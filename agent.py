import os
import re
import json
import base64
import fitz  # PyMuPDF
import tempfile
import datetime
from markitdown import MarkItDown
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gpt-4o"

# Maximum characters of AFS text to send to the LLM.
# ~4 chars per token, so 80,000 chars ≈ 20,000 tokens — leaves room for system prompt + images.
MAX_AFS_TEXT_CHARS = 80000

# Maximum file size per upload (15 MB)
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


def convert_pdf_to_base64_images(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        base64_images = []
        for page in doc:
            # matrix increases resolution for better OCR by OpenAI
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            base64_images.append(f"data:image/jpeg;base64,{b64}")
        return base64_images
    finally:
        doc.close()

def get_base64_from_bytes(file_bytes: bytes, mime_type: str):
    if "pdf" in mime_type:
        return convert_pdf_to_base64_images(file_bytes)
    else:
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        return [f"data:{mime_type};base64,{b64}"]


def validate_file_sizes(afs_bytes: bytes, aadhaar_list: list, pan_list: list):
    """Validate that no uploaded file exceeds the maximum allowed size."""
    if len(afs_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"AFS file is too large ({len(afs_bytes) / (1024*1024):.1f} MB). Maximum allowed is {MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB.")
    for i, item in enumerate(aadhaar_list):
        if len(item["bytes"]) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Aadhaar file #{i+1} is too large. Maximum allowed is {MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB.")
    for i, item in enumerate(pan_list):
        if len(item["bytes"]) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"PAN file #{i+1} is too large. Maximum allowed is {MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB.")


def _extract_last_json_block(text: str) -> dict | None:
    """Extract the LAST ```json ... ``` block from the response to avoid false matches."""
    json_blocks = re.findall(r'```json\s*(.*?)```', text, re.DOTALL)
    if json_blocks:
        return json.loads(json_blocks[-1].strip())
    return None


def verify_documents(afs_bytes: bytes, afs_mime: str, aadhaar_list: list, pan_list: list, afs_filename: str = "afs_document.pdf"):
    """
    Passes the documents to OpenAI (gpt-4o) to perform the KYC cross-verification
    based strictly on the system prompt rules.
    """
    # Validate file sizes before processing
    validate_file_sizes(afs_bytes, aadhaar_list, pan_list)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environment.")
        
    # Create client with a timeout to prevent indefinite hangs
    client = OpenAI(api_key=api_key, timeout=120.0)
    
    # Read the system prompt from the file we saved
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(current_dir, "system_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()
    except Exception as e:
        print(f"Warning: Could not read system_prompt.md: {e}")
        system_instruction = "You are a KYC Verification Agent. Verify that AFS matches KYC documents exactly."

    # Extract structured Markdown from AFS PDF using MarkItDown, falling back to PyMuPDF if needed
    afs_text = ""
    markdown_conversion_success = False
    conversion_error_msg = ""
    tmp_file_path = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(afs_bytes)
            tmp_file_path = tmp_file.name
        
        try:
            md = MarkItDown()
            result = md.convert(tmp_file_path)
            afs_text = result.text_content
            if afs_text.strip():
                markdown_conversion_success = True
        except Exception as e:
            conversion_error_msg = str(e)
            print(f"Warning: MarkItDown conversion failed, falling back to PyMuPDF: {e}")
    finally:
        # Always clean up temp file, even if MarkItDown crashes
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        
    if not markdown_conversion_success or not afs_text.strip():
        # Fallback to PyMuPDF
        try:
            doc = fitz.open(stream=afs_bytes, filetype="pdf")
            try:
                extracted_pages = []
                for page_num, page in enumerate(doc):
                    extracted_pages.append(f"--- PAGE {page_num + 1} ---\n{page.get_text()}")
                afs_text = "\n\n".join(extracted_pages)
            finally:
                doc.close()
        except Exception as pdf_err:
            afs_text = f"[ERROR CONVERTING AFS TO TEXT. MarkItDown error: {conversion_error_msg}. PyMuPDF error: {str(pdf_err)}]"

    # Truncate AFS text if it exceeds the maximum allowed characters to avoid blowing the context window
    afs_truncated = False
    if len(afs_text) > MAX_AFS_TEXT_CHARS:
        afs_text = afs_text[:MAX_AFS_TEXT_CHARS]
        afs_truncated = True

    # Save extracted text/markdown file to the extracted_markdowns folder
    try:
        output_dir = "extracted_markdowns"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(afs_filename)[0]
        md_filename = f"{timestamp}_{base_name}.md" if markdown_conversion_success else f"{timestamp}_{base_name}.txt"
        md_filepath = os.path.join(output_dir, md_filename)
        with open(md_filepath, "w", encoding="utf-8") as md_file:
            md_file.write(afs_text)
    except Exception as save_err:
        print(f"Warning: Could not save extracted text file: {save_err}")

    truncation_note = ""
    if afs_truncated:
        truncation_note = "\n    ⚠️ NOTE: The AFS text was very long and has been truncated. Some later pages may be missing. Focus on verifying the fields that are present.\n"

    prompt_text = f"""
    Please perform the full KYC verification for the provided documents.
    
    Document 1 is the Agreement for Sale (AFS). Below is the text content extracted from the AFS PDF:
    --- START AFS TEXT ---
    {afs_text}
    --- END AFS TEXT ---
    {truncation_note}
    We have provided the Aadhaar Card(s) and PAN Card(s) as images below.
    Note: Multiple Aadhaar Cards and/or PAN Cards may be provided for joint/co-applicants.
    
    Output the final Verification Report EXACTLY as specified in your instructions. Additionally, please return a JSON block at the very end of your response enclosed in ```json ... ``` with the following keys. DO NOT output any conversational text (like "Here is the JSON output") before the JSON block.
    - "status": "MATCH" or "MISMATCH" (Overall status)
    - "buyer_name": "Full name of the primary buyer"
    - "project_name": "Name of the project from AFS"
    - "unit_number": "Unit/Flat number from AFS"
    - "afs_date": "Date of the agreement"
    - "mismatches_text": "A brief summary of what mismatched (or 'None'). If there are missing KYC documents for co-applicants, output the exact warning string here."
    """

    messages = [
        {"role": "system", "content": system_instruction},
    ]

    # 2. Append the actual Base64 document payloads
    content_array = [{"type": "text", "text": prompt_text}]

    # Convert all Aadhaar and PAN documents to base64 images and append to content array
    for item in aadhaar_list:
        for b64 in get_base64_from_bytes(item["bytes"], item["mime"]):
            content_array.append({"type": "image_url", "image_url": {"url": b64}})
    for item in pan_list:
        for b64 in get_base64_from_bytes(item["bytes"], item["mime"]):
            content_array.append({"type": "image_url", "image_url": {"url": b64}})

    messages.append({"role": "user", "content": content_array})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.1,
        max_tokens=4096
    )
    
    text_response = response.choices[0].message.content
    
    # Extract JSON from the response — use the LAST json block to avoid false matches
    json_data = {}
    try:
        parsed = _extract_last_json_block(text_response)
        if parsed:
            json_data = parsed
            # Remove the last JSON block from the report shown to the user
            # Find the last ```json...``` and strip it
            last_json_start = text_response.rfind("```json")
            if last_json_start != -1:
                report_text = text_response[:last_json_start].strip()
                # Remove conversational filler like "Here is the JSON output:"
                lines = report_text.split('\n')
                while lines and ('json' in lines[-1].lower() or lines[-1].strip() == '' or lines[-1].strip() == '```'):
                    lines.pop()
                report_text = '\n'.join(lines).strip()
            else:
                report_text = text_response
        else:
            report_text = text_response
            # Fallback parsing
            json_data = {
                "status": "MISMATCH" if "❌ MISMATCH DETECTED" in report_text else "MATCH",
                "buyer_name": "Unknown",
                "project_name": "Unknown",
                "unit_number": "Unknown",
                "afs_date": "Unknown",
                "mismatches_text": "Failed to parse JSON. Please check report."
            }
    except Exception as e:
        report_text = text_response
        json_data = {"status": "MISMATCH", "error": str(e)}
        
    return report_text, json_data
