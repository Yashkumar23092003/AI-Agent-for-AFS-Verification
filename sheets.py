"""
sheets.py — Google Sheets integration for AFS <-> Sheet verification.
Reads data using a service account. No LLM, no comparison logic.
"""
import os
import json
import gspread
from google.oauth2 import service_account
from comparator import normalize_header

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_credentials() -> service_account.Credentials:
    """
    Loads the Google service account credentials.

    Resolution order (works both locally and in the cloud):
      1. GOOGLE_SHEETS_CREDENTIALS_JSON  — the full JSON *content* as a string
         (used on Streamlit Cloud / any host where you can't ship a file).
      2. GOOGLE_SHEETS_CREDENTIALS_PATH  — path to a JSON file on disk (local dev).
    """
    raw_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if raw_json and raw_json.strip():
        try:
            info = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(
                "GOOGLE_SHEETS_CREDENTIALS_JSON is set but is not valid JSON. "
                f"Parse error: {e}"
            )
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
    if not creds_path:
        raise ValueError(
            "No Google credentials configured. Set GOOGLE_SHEETS_CREDENTIALS_JSON "
            "(the JSON content) in the cloud, or GOOGLE_SHEETS_CREDENTIALS_PATH "
            "(a file path) locally."
        )
    if not os.path.isfile(creds_path):
        raise FileNotFoundError(f"Service account file not found: {creds_path}")
    return service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )


def get_worksheet(sheet_id: str, tab: str) -> gspread.Worksheet:
    """Opens a worksheet by Google Sheet ID and tab name."""
    gc = gspread.authorize(_get_credentials())
    spreadsheet = gc.open_by_key(sheet_id)
    return spreadsheet.worksheet(tab)


def find_unit_row(ws: gspread.Worksheet, unit_no: str) -> dict:
    """
    Searches the worksheet for the row matching unit_no in the first 'Unit No.' column.

    Returns a dict of {normalized_header: raw_cell_value}.
    For duplicate headers (e.g. 'Unit No.' appears twice), the value is a list of
    raw values in column-order.

    Raises ValueError if:
      - No 'Unit No.' column exists
      - The unit is not found
      - The unit appears in more than one row
    """
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        raise ValueError(
            "Sheet has fewer than 2 rows — expected at least a header row and one data row."
        )

    raw_headers = all_values[0]
    norm_headers = [normalize_header(h) for h in raw_headers]

    # Find indices of all 'unit no.' columns
    unit_no_indices = [i for i, h in enumerate(norm_headers) if h == "unit no."]
    if not unit_no_indices:
        raise ValueError(
            "No 'Unit No.' column found in sheet. "
            "Check that the header row contains 'Unit No.' exactly."
        )

    search_idx = unit_no_indices[0]
    unit_no_str = str(unit_no).strip()

    matching = []
    for row_num, row in enumerate(all_values[1:], start=2):
        cell = row[search_idx].strip() if search_idx < len(row) else ""
        if cell == unit_no_str:
            matching.append((row_num, row))

    if not matching:
        raise ValueError(
            f"Unit No. '{unit_no_str}' not found in sheet. "
            "Ensure the unit number matches exactly (case-sensitive, no leading zeros)."
        )
    if len(matching) > 1:
        row_nums = [r[0] for r in matching]
        raise ValueError(
            f"Unit No. '{unit_no_str}' found in multiple rows: {row_nums}. "
            "Sheet must contain unique unit numbers."
        )

    _, row = matching[0]

    # Build result dict; duplicate headers become lists
    result = {}
    for i, norm_h in enumerate(norm_headers):
        if not norm_h:       # skip blank-header columns
            continue
        raw_val = row[i] if i < len(row) else ""
        if norm_h in result:
            existing = result[norm_h]
            if isinstance(existing, list):
                existing.append(raw_val)
            else:
                result[norm_h] = [existing, raw_val]
        else:
            result[norm_h] = raw_val

    return result
