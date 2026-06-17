import os
import streamlit as st

# ── Secrets bootstrap ─────────────────────────────────────────────────────────
# On Streamlit Cloud, secrets live in st.secrets (NOT os.environ). Copy them into
# the environment BEFORE importing modules that read os.environ at import time
# (database.py reads DATABASE_URL; agent/notifier read API keys at call time).
# Locally this is a no-op — python-dotenv loads .env instead.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

import pandas as pd
from agent import (
    verify_documents,
    verify_afs_against_sheet,
    verify_full_verification,
    _sheet_prompt_is_placeholder,
)
from notifier import (
    generate_match_email,
    generate_mismatch_email,
    generate_sheet_audit_email,
    generate_full_verification_email,
)
from database import (
    init_db,
    save_verification, get_all_verifications_df, get_report_by_id,
    save_sheet_audit, get_all_sheet_audits_df, get_sheet_audit_by_id,
    save_full_verification, get_all_full_verifications_df, get_full_verification_by_id,
)
from pdf_report import generate_pdf_report, generate_sheet_audit_pdf, generate_full_verification_pdf
import ui

@st.cache_resource
def run_db_init():
    init_db()

run_db_init()

st.set_page_config(page_title="KYC Verification Agent", page_icon="🛡️", layout="wide")
ui.inject_css()

ui.hero(
    "Real Estate Verification Agent",
    "Upload Aadhaar, PAN and the Agreement for Sale once — the agent cross-checks identity "
    "and validates every figure against your Google Sheet, then delivers one clean verdict.",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    crm_email = st.text_input("CRM Officer Email", value=os.environ.get("SMTP_EMAIL", "crm@example.com"))
    default_sheet_id = os.environ.get("DEFAULT_SHEET_ID", "")
    st.markdown("---")
    st.markdown("#### What each tab does")
    st.markdown(
        "🛡️ **Full Verification** — KYC + Sheet in one run\n\n"
        "🪪 **KYC Only** — Identity check (Aadhaar/PAN vs AFS)\n\n"
        "🔢 **Sheet Audit Only** — Numeric fields vs Google Sheet\n\n"
        "📚 **History** — Every past record"
    )
    st.markdown("---")
    st.caption("Max file size: 15 MB per document.")

# ── Shared helpers ────────────────────────────────────────────────────────────
def _meta_items(buyer, unit, project, afs_date=None):
    items = [("Buyer", buyer or "—"), ("Unit", unit or "—"), ("Project", project or "—")]
    if afs_date is not None:
        items.append(("AFS Date", afs_date or "—"))
    return items


tab_full, tab_kyc, tab_sheet, tab_hist = st.tabs([
    "🛡️ Full Verification",
    "🪪 KYC Only",
    "🔢 Sheet Audit Only",
    "📚 History",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — FULL VERIFICATION
# ═════════════════════════════════════════════════════════════════════════════
with tab_full:
    if _sheet_prompt_is_placeholder():
        st.info(
            "⚙️ Sheet extraction prompt not configured — the sheet audit step will use the "
            "built-in **fixture (Unit 313)**. Fill in `afs_sheet_system_prompt.md` for live extraction."
        )

    with st.container(border=True):
        ui.section_label("📤", "Upload Documents")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            full_afs = st.file_uploader("Agreement for Sale (PDF)", type=["pdf"], key="full_afs")
        with col_f2:
            full_aadhaar = st.file_uploader(
                "Aadhaar Card(s)", type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True, key="full_aadhaar"
            )
        with col_f3:
            full_pan = st.file_uploader(
                "PAN Card(s)", type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True, key="full_pan"
            )

        ui.section_label("📑", "Google Sheet Source")
        col_fs1, col_fs2 = st.columns(2)
        with col_fs1:
            full_sheet_id = st.text_input("Google Sheet ID", value=default_sheet_id, key="full_sid")
        with col_fs2:
            full_tab_name = st.text_input("Sheet Tab Name", value="Sheet1", key="full_tab")

        with st.expander("⚙️ Developer options"):
            full_fixture = st.checkbox(
                "Force fixture (Unit 313 test data — skip live LLM extraction)",
                value=_sheet_prompt_is_placeholder(),
                key="full_fix",
            )

        run_full = st.button("🚀  Run Full Verification", type="primary", key="run_full", use_container_width=True)

    if run_full:
        if not full_afs or not full_aadhaar or not full_pan:
            st.warning("⚠️ Please upload AFS, Aadhaar Card(s) and PAN Card(s).")
        elif not full_sheet_id.strip() or not full_tab_name.strip():
            st.warning("⚠️ Please enter the Google Sheet ID and tab name.")
        else:
            aadhaar_list = [{"bytes": f.getvalue(), "mime": f.type, "filename": f.name} for f in full_aadhaar]
            pan_list     = [{"bytes": f.getvalue(), "mime": f.type, "filename": f.name} for f in full_pan]

            with st.spinner("🤖 Running KYC + Sheet audit… this can take up to ~90 seconds."):
                try:
                    result = verify_full_verification(
                        afs_bytes=full_afs.getvalue(),
                        afs_filename=full_afs.name,
                        afs_mime=full_afs.type,
                        aadhaar_list=aadhaar_list,
                        pan_list=pan_list,
                        sheet_id=full_sheet_id.strip(),
                        tab_name=full_tab_name.strip(),
                        use_fixture=full_fixture,
                    )
                except Exception as e:
                    st.error(f"❌ Verification failed: {e}")
                    st.stop()

            overall       = result["overall_verdict"]
            kyc_status    = result["kyc_status"]
            sheet_verdict = result["sheet_verdict"]
            kyc_json      = result["kyc_json"]
            buyer_name    = kyc_json.get("buyer_name", "Unknown")
            project_name  = kyc_json.get("project_name", "Unknown")
            afs_date      = kyc_json.get("afs_date", "Unknown")
            unit_no       = kyc_json.get("unit_number") or (
                result["extraction"].get("unit_number", {}).get("distinct_values", ["?"])[0]
            )

            if result.get("used_fixture"):
                st.info("ℹ️ Sheet audit used **fixture data** (Unit 313).")

            ui.verdict_banner(
                overall == "PASS",
                "Verification Passed" if overall == "PASS" else "Verification Failed",
                "Identity verified and all sheet values match."
                if overall == "PASS"
                else "One or more checks need review — see the breakdown below.",
            )
            ui.sub_verdict_pills(
                kyc_status == "MATCH", sheet_verdict == "PASS",
                kyc_status, sheet_verdict,
            )
            ui.meta_strip(_meta_items(buyer_name, unit_no, project_name, afs_date))

            with st.expander("🪪  Part 1 — KYC Identity Details", expanded=(kyc_status != "MATCH")):
                st.markdown(result["kyc_report_text"])

            with st.expander("🔢  Part 2 — Sheet Audit Details", expanded=(sheet_verdict != "PASS")):
                for w in result["sheet_warnings"]:
                    st.warning(f"⚠️ {w}")
                for c in result["sheet_schema_caveats"]:
                    st.info(f"ℹ️ Schema caveat: {c}")
                if result["sheet_fields"]:
                    ui.field_table(result["sheet_fields"])

            save_full_verification(
                unit_no=unit_no, buyer_name=buyer_name, project_name=project_name,
                afs_date=afs_date, kyc_status=kyc_status, sheet_verdict=sheet_verdict,
                overall_verdict=overall, kyc_report_text=result["kyc_report_text"],
                sheet_fields=result["sheet_fields"], afs_filename=full_afs.name,
                sheet_id=full_sheet_id.strip(), tab_name=full_tab_name.strip(),
            )
            st.toast("💾 Full verification saved to History!")

            email_ok = generate_full_verification_email(
                crm_email=crm_email, buyer_name=buyer_name, unit_no=unit_no,
                project_name=project_name, afs_date=afs_date, overall_verdict=overall,
                kyc_status=kyc_status, sheet_verdict=sheet_verdict,
                kyc_report_text=result["kyc_report_text"],
                sheet_fields=result["sheet_fields"],
                sheet_warnings=result["sheet_warnings"],
            )
            st.toast("📧 Email sent to CRM!" if email_ok else "⚠️ Email not sent — check SMTP in .env.")

            pdf_bytes = generate_full_verification_pdf(result)
            st.download_button(
                label="📥  Download Full Report (PDF)",
                data=pdf_bytes,
                file_name=f"FullVerification_{unit_no}_{buyer_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_full",
                use_container_width=True,
            )

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — KYC ONLY
# ═════════════════════════════════════════════════════════════════════════════
with tab_kyc:
    with st.container(border=True):
        ui.section_label("🪪", "KYC Identity Verification (Aadhaar / PAN vs AFS)")
        col1, col2, col3 = st.columns(3)
        with col1:
            afs_file = st.file_uploader("Agreement for Sale (AFS)", type=["pdf"], key="kyc_afs")
        with col2:
            aadhaar_files = st.file_uploader(
                "Aadhaar Card(s)", type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True, key="kyc_aad"
            )
        with col3:
            pan_files = st.file_uploader(
                "PAN Card(s)", type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True, key="kyc_pan"
            )
        run_kyc = st.button("🔍  Run KYC Verification", type="primary", key="run_kyc", use_container_width=True)

    if run_kyc:
        if not afs_file or not aadhaar_files or not pan_files:
            st.warning("⚠️ Please upload all required documents.")
        else:
            with st.spinner("🤖 Agent is analyzing documents…"):
                try:
                    aadhaar_list = [{"bytes": f.getvalue(), "mime": f.type, "filename": f.name} for f in aadhaar_files]
                    pan_list     = [{"bytes": f.getvalue(), "mime": f.type, "filename": f.name} for f in pan_files]
                    report_text, json_data = verify_documents(
                        afs_bytes=afs_file.getvalue(), afs_mime=afs_file.type,
                        aadhaar_list=aadhaar_list, pan_list=pan_list,
                        afs_filename=afs_file.name,
                    )
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.stop()

            status       = json_data.get("status", "MISMATCH")
            buyer_name   = json_data.get("buyer_name", "Unknown Client")
            project_name = json_data.get("project_name", "Unknown Project")
            unit_number  = json_data.get("unit_number", "Unknown Unit")
            afs_date     = json_data.get("afs_date", "Unknown Date")

            ui.verdict_banner(
                status == "MATCH",
                "All Fields Match" if status == "MATCH" else "Mismatch Detected",
                "The AFS is consistent with the KYC documents."
                if status == "MATCH"
                else "Discrepancies were found between the AFS and the KYC documents.",
            )
            ui.meta_strip(_meta_items(buyer_name, unit_number, project_name, afs_date))

            save_verification(buyer_name, project_name, unit_number, status, report_text)
            st.toast("💾 Record saved to History!")

            if status == "MATCH":
                email_ok = generate_match_email(crm_email, buyer_name, project_name, unit_number, afs_date, report_text)
            else:
                email_ok = generate_mismatch_email(
                    crm_email, buyer_name, project_name, unit_number, afs_date,
                    json_data.get("mismatches_text", "Please review the attached report."),
                    report_text,
                )
            st.toast("📧 Email sent to CRM!" if email_ok else "⚠️ Email not sent — check SMTP in .env.")

            pdf_bytes = generate_pdf_report(report_text, buyer_name, json_data=json_data)
            st.download_button(
                label="📥  Download Report (PDF)",
                data=pdf_bytes,
                file_name=f"KYC_Report_{buyer_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_kyc",
                use_container_width=True,
            )
            with st.expander("📄  Full Verification Report", expanded=True):
                st.markdown(report_text)

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — SHEET AUDIT ONLY
# ═════════════════════════════════════════════════════════════════════════════
with tab_sheet:
    if _sheet_prompt_is_placeholder():
        st.info(
            "⚙️ `afs_sheet_system_prompt.md` is a placeholder — using the built-in "
            "**fixture (Unit 313 / Rs.99,77,517 / 42.06 Sq.M / 453 Sq.Ft)**."
        )

    with st.container(border=True):
        ui.section_label("🔢", "AFS ↔ Google Sheet Audit")
        st.caption(
            "Verifies Agreement Value, Unit Number, Area Sq.M and Area Sq.Ft against the correct "
            "sheet row. Python does all normalization and comparison — no LLM math."
        )
        sheet_afs_file = st.file_uploader("Agreement for Sale (AFS)", type=["pdf"], key="sheet_afs")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            sheet_id_input = st.text_input("Google Sheet ID", value=default_sheet_id, key="sa_sid")
        with col_s2:
            tab_name_input = st.text_input("Sheet Tab Name", value="Sheet1", key="sa_tab")

        with st.expander("⚙️ Developer options"):
            use_fixture_cb = st.checkbox(
                "Force fixture (skip LLM extraction, use hardcoded Unit 313 data)",
                value=_sheet_prompt_is_placeholder(),
                key="sa_fix",
            )
        run_sa = st.button("🔍  Run Sheet Audit", type="primary", key="run_sa", use_container_width=True)

    if run_sa:
        if not sheet_afs_file:
            st.warning("⚠️ Please upload an AFS PDF.")
        elif not sheet_id_input.strip():
            st.warning("⚠️ Please enter a Google Sheet ID.")
        elif not tab_name_input.strip():
            st.warning("⚠️ Please enter the sheet tab name.")
        else:
            with st.spinner("🤖 Extracting from AFS and fetching sheet row…"):
                try:
                    result = verify_afs_against_sheet(
                        afs_bytes=sheet_afs_file.getvalue(),
                        afs_filename=sheet_afs_file.name,
                        sheet_id=sheet_id_input.strip(),
                        tab=tab_name_input.strip(),
                        use_fixture=use_fixture_cb,
                    )
                except Exception as e:
                    st.error(f"❌ Audit failed: {e}")
                    st.stop()

            verdict        = result["verdict"]
            fields         = result["fields"]
            warnings       = result["warnings"]
            schema_caveats = result["schema_caveats"]
            afs_meta       = result["afs_meta"]
            buyer_name     = afs_meta.get("buyer_name", "Unknown")
            project_name   = afs_meta.get("project_name", "Unknown")
            unit_no        = result["extraction"].get("unit_number", {}).get("distinct_values", ["?"])[0]

            if result["used_fixture"]:
                st.info("ℹ️ Results shown using **fixture data** (Unit 313).")

            ui.verdict_banner(
                verdict == "PASS",
                "Sheet Audit Passed" if verdict == "PASS" else "Sheet Audit Failed",
                "All verified fields match the Google Sheet."
                if verdict == "PASS"
                else "One or more fields do not match the Google Sheet.",
            )
            ui.meta_strip(_meta_items(buyer_name, unit_no, project_name))

            for w in warnings:
                st.warning(f"⚠️ {w}")
            for c in schema_caveats:
                st.info(f"ℹ️ Schema caveat: {c}")

            ui.section_label("📊", "Field-by-Field Results")
            ui.field_table(fields)

            save_sheet_audit(
                unit_no=unit_no, buyer_name=buyer_name, project_name=project_name,
                sheet_id=sheet_id_input.strip(), tab_name=tab_name_input.strip(),
                verdict=verdict, fields=fields, afs_filename=sheet_afs_file.name,
            )
            st.toast("💾 Audit record saved to History!")

            email_ok = generate_sheet_audit_email(
                crm_email, buyer_name, unit_no, project_name, verdict, fields, warnings,
            )
            st.toast("📧 Audit email sent to CRM!" if email_ok else "⚠️ Email not sent — check SMTP in .env.")

            pdf_bytes = generate_sheet_audit_pdf(result)
            st.download_button(
                label="📥  Download Audit Report (PDF)",
                data=pdf_bytes,
                file_name=f"SheetAudit_{unit_no}_{buyer_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_sa",
                use_container_width=True,
            )

# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ═════════════════════════════════════════════════════════════════════════════
with tab_hist:
    # ── Full verification history ─────────────────────────────────────────────
    with st.container(border=True):
        ui.section_label("🛡️", "Full Verifications")
        df_full = get_all_full_verifications_df()
        if df_full.empty:
            st.info("No full verifications yet. Use the 'Full Verification' tab.")
        else:
            df_full_disp = df_full.copy()
            df_full_disp["overall_verdict"] = df_full_disp["overall_verdict"].map(
                {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}).fillna(df_full_disp["overall_verdict"])
            df_full_disp["kyc_status"] = df_full_disp["kyc_status"].map(
                {"MATCH": "✅ MATCH", "MISMATCH": "❌ MISMATCH"}).fillna(df_full_disp["kyc_status"])
            df_full_disp["sheet_verdict"] = df_full_disp["sheet_verdict"].map(
                {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}).fillna(df_full_disp["sheet_verdict"])
            st.dataframe(
                df_full_disp,
                column_config={
                    "id": None, "date": "Date", "unit_no": "Unit",
                    "buyer_name": "Buyer", "project_name": "Project",
                    "kyc_status": "KYC", "sheet_verdict": "Sheet", "overall_verdict": "Overall",
                },
                use_container_width=True, hide_index=True,
            )
            full_opts = [
                f"ID {r['id']} — Unit {r['unit_no']} | {r['buyer_name']} ({r['date']})"
                for _, r in df_full.iterrows()
            ]
            sel_full = st.selectbox("View a record:", full_opts, key="full_hist_sel")
            if sel_full:
                fid = int(sel_full.split(" ")[1])
                frec = get_full_verification_by_id(fid)
                if frec:
                    ui.sub_verdict_pills(
                        frec.get("kyc_status") == "MATCH",
                        frec.get("sheet_verdict") == "PASS",
                        frec.get("kyc_status", "—"), frec.get("sheet_verdict", "—"),
                    )
                    with st.expander("🪪  KYC Report"):
                        st.markdown(frec.get("kyc_report_text", ""))
                    with st.expander("🔢  Sheet Field Table"):
                        if frec.get("sheet_per_field_json"):
                            ui.field_table(frec["sheet_per_field_json"])

    # ── KYC-only history ──────────────────────────────────────────────────────
    with st.container(border=True):
        ui.section_label("🪪", "KYC-Only Verifications")
        df_kyc = get_all_verifications_df()
        if df_kyc.empty:
            st.info("No KYC-only verifications yet.")
        else:
            df_kyc_disp = df_kyc.copy()
            df_kyc_disp["status"] = df_kyc_disp["status"].map(
                {"MATCH": "✅ MATCH", "MISMATCH": "❌ MISMATCH"}).fillna(df_kyc_disp["status"])
            st.dataframe(
                df_kyc_disp,
                column_config={
                    "id": None, "date": "Date & Time", "buyer_name": "Buyer",
                    "project_name": "Project", "unit_number": "Unit", "status": "Status",
                },
                use_container_width=True, hide_index=True,
            )
            kyc_opts = [f"ID {r['id']} - {r['buyer_name']} ({r['date']})" for _, r in df_kyc.iterrows()]
            sel_kyc = st.selectbox("View a record:", kyc_opts, key="kyc_hist_sel")
            if sel_kyc:
                rid = int(sel_kyc.split(" ")[1])
                rpt = get_report_by_id(rid)
                try:
                    name_part = sel_kyc.split(" - ")[1].split(" (")[0]
                except Exception:
                    name_part = f"Record_{rid}"
                hist_row = df_kyc[df_kyc["id"] == rid].iloc[0]
                hist_json = {
                    "buyer_name":   hist_row.get("buyer_name", name_part),
                    "project_name": hist_row.get("project_name", "—"),
                    "unit_number":  hist_row.get("unit_number", "—"),
                    "afs_date":     hist_row.get("afs_date", "—"),
                    "status":       hist_row.get("status", "MISMATCH"),
                }
                pdf_b = generate_pdf_report(rpt, name_part, json_data=hist_json)
                st.download_button(
                    label="📥  Download Report (PDF)", data=pdf_b,
                    file_name=f"KYC_Report_{name_part.replace(' ', '_')}.pdf",
                    mime="application/pdf", key=f"dl_kyc_hist_{rid}",
                )
                with st.expander("📄  Full Report"):
                    st.markdown(rpt)

    # ── Sheet audit history ───────────────────────────────────────────────────
    with st.container(border=True):
        ui.section_label("🔢", "Sheet Audit-Only History")
        df_audits = get_all_sheet_audits_df()
        if df_audits.empty:
            st.info("No sheet audits yet.")
        else:
            df_aud_disp = df_audits.copy()
            df_aud_disp["verdict"] = df_aud_disp["verdict"].map(
                {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}).fillna(df_aud_disp["verdict"])
            st.dataframe(
                df_aud_disp,
                column_config={
                    "id": None, "date": "Date", "unit_no": "Unit", "buyer_name": "Buyer",
                    "project_name": "Project", "verdict": "Verdict",
                },
                use_container_width=True, hide_index=True,
            )
            aud_opts = [
                f"ID {r['id']} — Unit {r['unit_no']} | {r['buyer_name']} ({r['date']})"
                for _, r in df_audits.iterrows()
            ]
            sel_aud = st.selectbox("View an audit record:", aud_opts, key="aud_sel")
            if sel_aud:
                aid = int(sel_aud.split(" ")[1])
                arec = get_sheet_audit_by_id(aid)
                if arec and arec.get("per_field_json"):
                    ui.field_table(arec["per_field_json"])

ui.footer()
