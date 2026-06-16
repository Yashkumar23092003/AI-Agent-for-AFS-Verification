import streamlit as st
import os
from agent import verify_documents
from notifier import generate_match_email, generate_mismatch_email
from database import init_db, save_verification, get_all_verifications_df, get_report_by_id
from pdf_report import generate_pdf_report

# Initialize database once
@st.cache_resource
def run_db_init():
    init_db()

run_db_init()

st.set_page_config(page_title="KYC Verification Agent", page_icon="📋", layout="wide")

st.title("📋 Real Estate KYC Verification Agent")
st.markdown("Upload the client's Agreement for Sale (AFS) and their KYC documents. The agent will cross-verify every field and automatically email the CRM team.")

with st.sidebar:
    st.header("Settings")
    crm_email = st.text_input("CRM Officer Email", value=os.environ.get("SMTP_EMAIL", "crm@example.com"))
    
    st.markdown("---")
    st.markdown("**Instructions:**")
    st.markdown("1. Upload the AFS (PDF format).")
    st.markdown("2. Upload Aadhaar Card(s) (Image or PDF). Upload multiple for co-applicants.")
    st.markdown("3. Upload PAN Card(s) (Image or PDF). Upload multiple for co-applicants.")
    st.markdown("4. Click **Run Verification**.")
    st.markdown("---")
    st.caption("⚠️ Max file size: 15 MB per document.")

tab1, tab2 = st.tabs(["🆕 New Verification", "📚 Verification History"])

with tab1:
    col1, col2, col3 = st.columns(3)

    with col1:
        afs_file = st.file_uploader("1. Agreement for Sale (AFS)", type=["pdf"])

    with col2:
        aadhaar_files = st.file_uploader("2. Aadhaar Card(s) (Upload multiple for co-applicants)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

    with col3:
        pan_files = st.file_uploader("3. PAN Card(s) (Upload multiple for co-applicants)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

    if st.button("🔍 Run Verification", type="primary"):
        if not afs_file or not aadhaar_files or not pan_files:
            st.warning("⚠️ Please upload all required documents (AFS, Aadhaar Card(s), PAN Card(s)) to proceed.")
        else:
            with st.spinner("🤖 Agent is analyzing documents... This may take a minute."):
                try:
                    # Prepare lists of uploaded KYC documents
                    aadhaar_list = []
                    for f in aadhaar_files:
                        aadhaar_list.append({
                            "bytes": f.getvalue(),
                            "mime": f.type,
                            "filename": f.name
                        })
                        
                    pan_list = []
                    for f in pan_files:
                        pan_list.append({
                            "bytes": f.getvalue(),
                            "mime": f.type,
                            "filename": f.name
                        })

                    report_text, json_data = verify_documents(
                        afs_bytes=afs_file.getvalue(),
                        afs_mime=afs_file.type,
                        aadhaar_list=aadhaar_list,
                        pan_list=pan_list,
                        afs_filename=afs_file.name
                    )
                    
                    st.success("Verification Complete!")
                    
                    # Handle Email Trigger and Data Extraction
                    st.subheader("Action Taken")
                    status = json_data.get("status", "MISMATCH")
                    buyer_name = json_data.get("buyer_name", "Unknown Client")
                    project_name = json_data.get("project_name", "Unknown Project")
                    unit_number = json_data.get("unit_number", "Unknown Unit")
                    afs_date = json_data.get("afs_date", "Unknown Date")
                    
                    # Save to history database
                    save_verification(buyer_name, project_name, unit_number, status, report_text)
                    st.toast("💾 Record saved to History!")
                    
                    if status == "MATCH":
                        st.info("✅ All fields match. Triggering success email to CRM.")
                        success = generate_match_email(
                            crm_email=crm_email,
                            buyer_name=buyer_name,
                            project_name=project_name,
                            unit_number=unit_number,
                            afs_date=afs_date,
                            report_text=report_text
                        )
                    else:
                        st.error("❌ Mismatches found. Triggering action-required email to CRM.")
                        success = generate_mismatch_email(
                            crm_email=crm_email,
                            buyer_name=buyer_name,
                            project_name=project_name,
                            unit_number=unit_number,
                            afs_date=afs_date,
                            mismatches_text=json_data.get("mismatches_text", "Please review the attached report for mismatches."),
                            report_text=report_text
                        )
                    
                    if success:
                        st.toast("📧 Email successfully sent to CRM!")
                    else:
                        st.warning("⚠️ Could not send email. Please check your SMTP credentials in the .env file.")
                        
                    # Display the report
                    st.subheader("Verification Report")
                    # Generate PDF for download
                    pdf_bytes = generate_pdf_report(report_text, buyer_name, json_data=json_data)
                    st.download_button(
                        label="📥 Download Report as PDF",
                        data=pdf_bytes,
                        file_name=f"KYC_Report_{buyer_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key="download_new_report"
                    )
                    st.markdown(report_text)
                        
                except Exception as e:
                    st.error(f"An error occurred during verification: {e}")

with tab2:
    st.header("Past Verifications")
    df = get_all_verifications_df()
    
    if df.empty:
        st.info("No past verifications found. Run a verification to see it here!")
    else:
        # Show table with formatted status and columns
        df_display = df.copy()
        df_display["status"] = df_display["status"].map({
            "MATCH": "✅ MATCH",
            "MISMATCH": "❌ MISMATCH"
        }).fillna(df_display["status"])
        
        st.dataframe(
            df_display,
            column_config={
                "id": None,  # Hide ID column
                "date": "Date & Time",
                "buyer_name": "Buyer Name",
                "project_name": "Project Name",
                "unit_number": "Unit/Flat",
                "status": "Status"
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("---")
        st.subheader("View Full Report")
        
        # Let user select a record to view the full text
        record_options = [f"ID {row['id']} - {row['buyer_name']} ({row['date']})" for _, row in df.iterrows()]
        selected_record = st.selectbox("Select a record to view its full report:", record_options)
        
        if selected_record:
            # Extract ID from the selection
            record_id = int(selected_record.split(" ")[1])
            report_text = get_report_by_id(record_id)
            
            # Extract buyer name from selected record text for cleaner file name
            try:
                name_part = selected_record.split(" - ")[1].split(" (")[0]
            except Exception:
                name_part = f"Record_{record_id}"
                
            # Reconstruct minimal json_data from the history row for the cover page
            history_row = df[df["id"] == record_id].iloc[0]
            history_json = {
                "buyer_name": history_row.get("buyer_name", name_part),
                "project_name": history_row.get("project_name", "—"),
                "unit_number": history_row.get("unit_number", "—"),
                "afs_date": history_row.get("afs_date", "—"),
                "status": history_row.get("status", "MISMATCH"),
            }
            # Generate PDF for download
            pdf_bytes = generate_pdf_report(report_text, name_part, json_data=history_json)
            st.download_button(
                label="📥 Download Report as PDF",
                data=pdf_bytes,
                file_name=f"KYC_Report_{name_part.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_history_{record_id}"
            )
            st.markdown(report_text)
