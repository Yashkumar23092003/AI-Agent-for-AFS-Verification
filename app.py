import streamlit as st
import os
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
from comparator import MATCH, MISMATCH, SCHEMA_CAVEAT, INTERNAL_DISCREPANCY, NOT_FOUND_IN_AFS, NOT_FOUND_IN_SHEET

@st.cache_resource
def run_db_init():
    init_db()

run_db_init()

st.set_page_config(page_title="KYC Verification Agent", page_icon="📋", layout="wide")
st.title("📋 Real Estate KYC Verification Agent")
st.markdown("Upload client documents. The agent cross-verifies KYC identity and AFS numeric fields against the Google Sheet.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    crm_email = st.text_input("CRM Officer Email", value=os.environ.get("SMTP_EMAIL", "crm@example.com"))
    default_sheet_id = os.environ.get("DEFAULT_SHEET_ID", "")
    st.markdown("---")
    st.markdown("**Tabs:**")
    st.markdown("- **Full Verification** — KYC + Sheet in one go")
    st.markdown("- **KYC Only** — Identity check (Aadhaar/PAN vs AFS)")
    st.markdown("- **Sheet Audit Only** — Numeric fields vs Google Sheet")
    st.markdown("- **History** — All past records")
    st.markdown("---")
    st.caption("Max file size: 15 MB per document.")

# ── Shared helpers ────────────────────────────────────────────────────────────
STATUS_EMOJI = {
    MATCH:                "✅ MATCH",
    MISMATCH:             "❌ MISMATCH",
    SCHEMA_CAVEAT:        "⚠️ SCHEMA CAVEAT",
    INTERNAL_DISCREPANCY: "🔴 INTERNAL DISCREPANCY",
    NOT_FOUND_IN_AFS:     "❓ NOT IN AFS",
    NOT_FOUND_IN_SHEET:   "❓ NOT IN SHEET",
}

def _colour_status(val):
    if "MATCH" in val and "MISMATCH" not in val:
        return "background-color: #d1fae5; color: #065f46;"
    if "MISMATCH" in val or "DISCREPANCY" in val:
        return "background-color: #fee2e2; color: #991b1b;"
    if "CAVEAT" in val or "NOT IN" in val:
        return "background-color: #fef3c7; color: #92400e;"
    return ""


def _sheet_fields_dataframe(fields):
    rows = []
    for f in fields:
        afs_raw = "; ".join(
            f"{o.get('location','')}: {o.get('raw_text','')}"
            for o in f.afs_occurrences
        ) or " | ".join(f.afs_distinct_values)
        rows.append({
            "Status":          STATUS_EMOJI.get(f.status, f.status),
            "Field":           f.field_name,
            "AFS Raw":         afs_raw,
            "Sheet Raw":       str(f.sheet_raw),
            "AFS Norm.":       str(f.afs_normalized) if f.afs_normalized else "—",
            "Sheet Norm.":     str(f.sheet_normalized) if f.sheet_normalized else "—",
            "Detail / Notes":  f.detail or "",
        })
    df = pd.DataFrame(rows)
    return df.style.map(_colour_status, subset=["Status"])


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_full, tab_kyc, tab_sheet, tab_hist = st.tabs([
    "✅ Full Verification",
    "🪪 KYC Only",
    "🔢 Sheet Audit Only",
    "📚 History",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — FULL VERIFICATION
# ═════════════════════════════════════════════════════════════════════════════
with tab_full:
    st.header("Full End-to-End Verification")
    st.markdown(
        "Upload Aadhaar, PAN and AFS once. "
        "The agent runs **KYC identity check** and **Sheet numeric audit** together — "
        "two separate LLM calls, same accuracy as running them individually."
    )

    if _sheet_prompt_is_placeholder():
        st.warning(
            "⚙️ **Sheet extraction prompt not configured.** "
            "The sheet audit step will use the **built-in fixture** (Unit 313). "
            "Fill in `afs_sheet_system_prompt.md` to enable live extraction."
        )

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        full_afs = st.file_uploader("1. AFS (PDF)", type=["pdf"], key="full_afs")
    with col_f2:
        full_aadhaar = st.file_uploader(
            "2. Aadhaar Card(s)", type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True, key="full_aadhaar"
        )
    with col_f3:
        full_pan = st.file_uploader(
            "3. PAN Card(s)", type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True, key="full_pan"
        )

    col_fs1, col_fs2 = st.columns(2)
    with col_fs1:
        full_sheet_id = st.text_input("4. Google Sheet ID", value=default_sheet_id, key="full_sid")
    with col_fs2:
        full_tab_name = st.text_input("5. Sheet Tab Name", value="Sheet1", key="full_tab")

    with st.expander("⚙️ Developer options"):
        full_fixture = st.checkbox(
            "Force fixture (Unit 313 test data — skip live LLM extraction)",
            value=_sheet_prompt_is_placeholder(),
            key="full_fix",
        )

    if st.button("🔍 Run Full Verification", type="primary", key="run_full"):
        if not full_afs or not full_aadhaar or not full_pan:
            st.warning("⚠️ Please upload AFS, Aadhaar Card(s) and PAN Card(s).")
        elif not full_sheet_id.strip() or not full_tab_name.strip():
            st.warning("⚠️ Please enter the Google Sheet ID and tab name.")
        else:
            aadhaar_list = [{"bytes": f.getvalue(), "mime": f.type, "filename": f.name} for f in full_aadhaar]
            pan_list     = [{"bytes": f.getvalue(), "mime": f.type, "filename": f.name} for f in full_pan]

            with st.spinner("🤖 Running KYC + Sheet audit (two LLM calls)… This may take ~90 seconds."):
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
                st.info("ℹ️ Sheet audit used **fixture data** (Unit 313). Live extraction requires a configured prompt.")

            # Overall verdict
            if overall == "PASS":
                st.success("✅ **OVERALL: PASS** — Identity verified AND all sheet values match.")
            else:
                st.error("❌ **OVERALL: FAIL** — One or more checks failed (see details below).")

            # Sub-verdict row
            col_k, col_s = st.columns(2)
            with col_k:
                if kyc_status == "MATCH":
                    st.success("✅ **Part 1 — KYC: MATCH**")
                else:
                    st.error("❌ **Part 1 — KYC: MISMATCH**")
            with col_s:
                if sheet_verdict == "PASS":
                    st.success("✅ **Part 2 — Sheet Audit: PASS**")
                else:
                    st.error("❌ **Part 2 — Sheet Audit: FAIL**")

            # KYC details
            with st.expander("Part 1: KYC Verification Details", expanded=(kyc_status != "MATCH")):
                st.markdown(result["kyc_report_text"])

            # Sheet details
            with st.expander("Part 2: Sheet Audit Details", expanded=(sheet_verdict != "PASS")):
                for w in result["sheet_warnings"]:
                    st.warning(f"⚠️ {w}")
                for c in result["sheet_schema_caveats"]:
                    st.info(f"ℹ️ Schema caveat: {c}")
                if result["sheet_fields"]:
                    st.dataframe(
                        _sheet_fields_dataframe(result["sheet_fields"]),
                        use_container_width=True, hide_index=True,
                    )

            # Save
            save_full_verification(
                unit_no=unit_no, buyer_name=buyer_name, project_name=project_name,
                afs_date=afs_date, kyc_status=kyc_status, sheet_verdict=sheet_verdict,
                overall_verdict=overall, kyc_report_text=result["kyc_report_text"],
                sheet_fields=result["sheet_fields"], afs_filename=full_afs.name,
                sheet_id=full_sheet_id.strip(), tab_name=full_tab_name.strip(),
            )
            st.toast("💾 Full verification saved to History!")

            # Email
            email_ok = generate_full_verification_email(
                crm_email=crm_email, buyer_name=buyer_name, unit_no=unit_no,
                project_name=project_name, afs_date=afs_date, overall_verdict=overall,
                kyc_status=kyc_status, sheet_verdict=sheet_verdict,
                kyc_report_text=result["kyc_report_text"],
                sheet_fields=result["sheet_fields"],
                sheet_warnings=result["sheet_warnings"],
            )
            if email_ok:
                st.toast("📧 Full verification email sent to CRM!")
            else:
                st.warning("⚠️ Could not send email. Check SMTP credentials in .env.")

            # PDF
            pdf_bytes = generate_full_verification_pdf(result)
            st.download_button(
                label="📥 Download Full Report as PDF",
                data=pdf_bytes,
                file_name=f"FullVerification_{unit_no}_{buyer_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_full",
            )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — KYC ONLY
# ═════════════════════════════════════════════════════════════════════════════
with tab_kyc:
    st.header("KYC Identity Verification (Aadhaar / PAN vs AFS)")

    col1, col2, col3 = st.columns(3)
    with col1:
        afs_file = st.file_uploader("1. Agreement for Sale (AFS)", type=["pdf"], key="kyc_afs")
    with col2:
        aadhaar_files = st.file_uploader(
            "2. Aadhaar Card(s) (multiple for co-applicants)",
            type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key="kyc_aad"
        )
    with col3:
        pan_files = st.file_uploader(
            "3. PAN Card(s) (multiple for co-applicants)",
            type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key="kyc_pan"
        )

    if st.button("🔍 Run KYC Verification", type="primary", key="run_kyc"):
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

            st.success("Verification Complete!")
            status       = json_data.get("status", "MISMATCH")
            buyer_name   = json_data.get("buyer_name", "Unknown Client")
            project_name = json_data.get("project_name", "Unknown Project")
            unit_number  = json_data.get("unit_number", "Unknown Unit")
            afs_date     = json_data.get("afs_date", "Unknown Date")

            save_verification(buyer_name, project_name, unit_number, status, report_text)
            st.toast("💾 Record saved to History!")

            if status == "MATCH":
                st.info("✅ All fields match. Sending success email to CRM.")
                email_ok = generate_match_email(crm_email, buyer_name, project_name, unit_number, afs_date, report_text)
            else:
                st.error("❌ Mismatches found. Sending action-required email to CRM.")
                email_ok = generate_mismatch_email(
                    crm_email, buyer_name, project_name, unit_number, afs_date,
                    json_data.get("mismatches_text", "Please review the attached report."),
                    report_text,
                )
            if email_ok:
                st.toast("📧 Email sent to CRM!")
            else:
                st.warning("⚠️ Could not send email. Check SMTP credentials in .env.")

            pdf_bytes = generate_pdf_report(report_text, buyer_name, json_data=json_data)
            st.download_button(
                label="📥 Download Report as PDF",
                data=pdf_bytes,
                file_name=f"KYC_Report_{buyer_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_kyc",
            )
            st.subheader("Verification Report")
            st.markdown(report_text)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — SHEET AUDIT ONLY
# ═════════════════════════════════════════════════════════════════════════════
with tab_sheet:
    st.header("AFS ↔ Google Sheet Audit")
    st.markdown(
        "Upload an AFS PDF and verify its **Agreement Value, Unit Number, Area Sq.M, and Area Sq.Ft** "
        "against the correct row in your Google Sheet. Python does all normalization and comparison — no LLM math."
    )

    if _sheet_prompt_is_placeholder():
        st.warning(
            "⚙️ **Extraction prompt not configured.** "
            "`afs_sheet_system_prompt.md` is still a placeholder. "
            "The app will use the **built-in fixture** (Unit 313 / Rs.99,77,517 / 42.06 Sq.M / 453 Sq.Ft). "
            "Replace the file with a real prompt to enable live extraction."
        )

    sheet_afs_file = st.file_uploader("1. Agreement for Sale (AFS)", type=["pdf"], key="sheet_afs")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        sheet_id_input = st.text_input("2. Google Sheet ID", value=default_sheet_id, key="sa_sid")
    with col_s2:
        tab_name_input = st.text_input("3. Sheet Tab Name", value="Sheet1", key="sa_tab")

    with st.expander("⚙️ Developer options"):
        use_fixture_cb = st.checkbox(
            "Force fixture (skip LLM extraction, use hardcoded Unit 313 data)",
            value=_sheet_prompt_is_placeholder(),
            key="sa_fix",
        )

    if st.button("🔍 Run Sheet Audit", type="primary", key="run_sa"):
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

            verdict       = result["verdict"]
            fields        = result["fields"]
            warnings      = result["warnings"]
            schema_caveats = result["schema_caveats"]
            afs_meta      = result["afs_meta"]
            buyer_name    = afs_meta.get("buyer_name", "Unknown")
            project_name  = afs_meta.get("project_name", "Unknown")
            unit_no       = result["extraction"].get("unit_number", {}).get("distinct_values", ["?"])[0]

            if result["used_fixture"]:
                st.info("ℹ️ Results shown using **fixture data** (Unit 313).")

            if verdict == "PASS":
                st.success("✅ **PASS** — All verified fields match the Google Sheet.")
            else:
                st.error("❌ **FAIL** — One or more fields do not match the Google Sheet.")

            for w in warnings:
                st.warning(f"⚠️ {w}")
            for c in schema_caveats:
                st.info(f"ℹ️ Schema caveat: {c}")

            st.subheader("Field-by-Field Results")
            st.dataframe(
                _sheet_fields_dataframe(fields),
                use_container_width=True, hide_index=True,
            )

            save_sheet_audit(
                unit_no=unit_no, buyer_name=buyer_name, project_name=project_name,
                sheet_id=sheet_id_input.strip(), tab_name=tab_name_input.strip(),
                verdict=verdict, fields=fields, afs_filename=sheet_afs_file.name,
            )
            st.toast("💾 Audit record saved to History!")

            email_ok = generate_sheet_audit_email(
                crm_email, buyer_name, unit_no, project_name, verdict, fields, warnings,
            )
            if email_ok:
                st.toast("📧 Audit email sent to CRM!")
            else:
                st.warning("⚠️ Could not send email. Check SMTP credentials in .env.")

            pdf_bytes = generate_sheet_audit_pdf(result)
            st.download_button(
                label="📥 Download Audit Report as PDF",
                data=pdf_bytes,
                file_name=f"SheetAudit_{unit_no}_{buyer_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_sa",
            )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ═════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.header("Verification History")

    # ── Full verification history ─────────────────────────────────────────────
    st.subheader("Full Verifications")
    df_full = get_all_full_verifications_df()
    if df_full.empty:
        st.info("No full verifications yet. Use the 'Full Verification' tab.")
    else:
        df_full_disp = df_full.copy()
        df_full_disp["overall_verdict"] = df_full_disp["overall_verdict"].map(
            {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}
        ).fillna(df_full_disp["overall_verdict"])
        df_full_disp["kyc_status"] = df_full_disp["kyc_status"].map(
            {"MATCH": "✅ MATCH", "MISMATCH": "❌ MISMATCH"}
        ).fillna(df_full_disp["kyc_status"])
        df_full_disp["sheet_verdict"] = df_full_disp["sheet_verdict"].map(
            {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}
        ).fillna(df_full_disp["sheet_verdict"])
        st.dataframe(
            df_full_disp,
            column_config={
                "id": None, "date": "Date", "unit_no": "Unit",
                "buyer_name": "Buyer", "project_name": "Project",
                "kyc_status": "KYC", "sheet_verdict": "Sheet",
                "overall_verdict": "Overall",
            },
            use_container_width=True, hide_index=True,
        )
        st.markdown("**View Full Verification Record**")
        full_opts = [
            f"ID {r['id']} — Unit {r['unit_no']} | {r['buyer_name']} ({r['date']})"
            for _, r in df_full.iterrows()
        ]
        sel_full = st.selectbox("Select a record:", full_opts, key="full_hist_sel")
        if sel_full:
            fid = int(sel_full.split(" ")[1])
            frec = get_full_verification_by_id(fid)
            if frec:
                c1, c2 = st.columns(2)
                with c1:
                    v = frec.get("kyc_status", "")
                    (st.success if v == "MATCH" else st.error)(f"KYC: {v}")
                with c2:
                    v = frec.get("sheet_verdict", "")
                    (st.success if v == "PASS" else st.error)(f"Sheet: {v}")

                with st.expander("KYC Report"):
                    st.markdown(frec.get("kyc_report_text", ""))
                with st.expander("Sheet Field Table"):
                    audit_fields = frec.get("sheet_per_field_json", [])
                    STATUS_EMOJI_H = {
                        "MATCH": "✅ MATCH", "MISMATCH": "❌ MISMATCH",
                        "SCHEMA_CAVEAT": "⚠️ CAVEAT",
                        "INTERNAL_DISCREPANCY": "🔴 DISCREPANCY",
                        "NOT_FOUND_IN_AFS": "❓ NOT IN AFS",
                        "NOT_FOUND_IN_SHEET": "❓ NOT IN SHEET",
                    }
                    rows_h = [{
                        "Status": STATUS_EMOJI_H.get(f.get("status", ""), f.get("status", "")),
                        "Field": f.get("field_name", ""),
                        "AFS Value": " | ".join(str(v) for v in f.get("afs_distinct_values", [])),
                        "Sheet Raw": str(f.get("sheet_raw", "")),
                        "AFS Norm.": str(f.get("afs_normalized") or "—"),
                        "Sheet Norm.": str(f.get("sheet_normalized") or "—"),
                        "Notes": f.get("detail", ""),
                    } for f in audit_fields]
                    if rows_h:
                        st.dataframe(pd.DataFrame(rows_h), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── KYC-only history ──────────────────────────────────────────────────────
    st.subheader("KYC-Only Verifications")
    df_kyc = get_all_verifications_df()
    if df_kyc.empty:
        st.info("No KYC-only verifications yet.")
    else:
        df_kyc_disp = df_kyc.copy()
        df_kyc_disp["status"] = df_kyc_disp["status"].map(
            {"MATCH": "✅ MATCH", "MISMATCH": "❌ MISMATCH"}
        ).fillna(df_kyc_disp["status"])
        st.dataframe(
            df_kyc_disp,
            column_config={
                "id": None, "date": "Date & Time", "buyer_name": "Buyer",
                "project_name": "Project", "unit_number": "Unit", "status": "Status",
            },
            use_container_width=True, hide_index=True,
        )
        st.markdown("**View Full KYC Report**")
        kyc_opts = [f"ID {r['id']} - {r['buyer_name']} ({r['date']})" for _, r in df_kyc.iterrows()]
        sel_kyc = st.selectbox("Select a record:", kyc_opts, key="kyc_hist_sel")
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
                label="📥 Download Report as PDF", data=pdf_b,
                file_name=f"KYC_Report_{name_part.replace(' ', '_')}.pdf",
                mime="application/pdf", key=f"dl_kyc_hist_{rid}",
            )
            st.markdown(rpt)

    st.markdown("---")

    # ── Sheet audit history ───────────────────────────────────────────────────
    st.subheader("Sheet Audit-Only History")
    df_audits = get_all_sheet_audits_df()
    if df_audits.empty:
        st.info("No sheet audits yet.")
    else:
        df_aud_disp = df_audits.copy()
        df_aud_disp["verdict"] = df_aud_disp["verdict"].map(
            {"PASS": "✅ PASS", "FAIL": "❌ FAIL"}
        ).fillna(df_aud_disp["verdict"])
        st.dataframe(
            df_aud_disp,
            column_config={
                "id": None, "date": "Date", "unit_no": "Unit", "buyer_name": "Buyer",
                "project_name": "Project", "verdict": "Verdict",
            },
            use_container_width=True, hide_index=True,
        )
        st.markdown("**View Full Audit Record**")
        aud_opts = [
            f"ID {r['id']} — Unit {r['unit_no']} | {r['buyer_name']} ({r['date']})"
            for _, r in df_audits.iterrows()
        ]
        sel_aud = st.selectbox("Select an audit record:", aud_opts, key="aud_sel")
        if sel_aud:
            aid = int(sel_aud.split(" ")[1])
            arec = get_sheet_audit_by_id(aid)
            if arec:
                STATUS_EMOJI_A = {
                    "MATCH": "✅ MATCH", "MISMATCH": "❌ MISMATCH",
                    "SCHEMA_CAVEAT": "⚠️ CAVEAT",
                    "INTERNAL_DISCREPANCY": "🔴 DISCREPANCY",
                    "NOT_FOUND_IN_AFS": "❓ NOT IN AFS",
                    "NOT_FOUND_IN_SHEET": "❓ NOT IN SHEET",
                }
                rows_a = [{
                    "Status": STATUS_EMOJI_A.get(f.get("status", ""), f.get("status", "")),
                    "Field": f.get("field_name", ""),
                    "AFS Value": " | ".join(str(v) for v in f.get("afs_distinct_values", [])),
                    "Sheet Raw": str(f.get("sheet_raw", "")),
                    "AFS Norm.": str(f.get("afs_normalized") or "—"),
                    "Sheet Norm.": str(f.get("sheet_normalized") or "—"),
                    "Notes": f.get("detail", ""),
                } for f in arec.get("per_field_json", [])]
                if rows_a:
                    st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)
