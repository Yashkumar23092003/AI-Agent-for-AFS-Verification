"""
ui.py — Presentation helpers for the Streamlit app.
Pure rendering: no verification logic lives here.
"""
import html
import streamlit as st

# ── Brand palette (aligned with the PDF report) ───────────────────────────────
NAVY = "#0f2850"
INDIGO = "#4f46e5"
BLUE = "#2563eb"
GREEN = "#10b981"
GREEN_DK = "#065f46"
RED = "#ef4444"
RED_DK = "#991b1b"
AMBER = "#f59e0b"
AMBER_DK = "#92400e"
SLATE = "#64748b"


GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---- base ---- */
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.stApp {
    background:
        radial-gradient(1100px 480px at 12% -8%, #eef2ff 0%, rgba(238,242,255,0) 60%),
        radial-gradient(1000px 460px at 100% 0%, #ecfeff 0%, rgba(236,254,255,0) 55%),
        #f7f9fc;
}
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1180px; }

/* ---- hide default chrome ---- */
#MainMenu, footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* ---- headings ---- */
h1, h2, h3 { color: #0f172a; letter-spacing: -0.02em; font-weight: 700; }

/* ---- hero ---- */
.hero {
    position: relative;
    border-radius: 22px;
    padding: 34px 38px;
    margin-bottom: 22px;
    background: linear-gradient(125deg, #0b1f44 0%, #15306a 45%, #3730a3 100%);
    box-shadow: 0 18px 45px -18px rgba(15,40,80,0.55);
    overflow: hidden;
}
.hero::after {
    content: ""; position: absolute; right: -60px; top: -60px;
    width: 280px; height: 280px; border-radius: 50%;
    background: radial-gradient(circle, rgba(99,102,241,0.55), rgba(99,102,241,0) 70%);
}
.hero-badge {
    display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 0.14em;
    color: #c7d2fe; background: rgba(199,210,254,0.14);
    border: 1px solid rgba(199,210,254,0.3);
    padding: 5px 12px; border-radius: 999px; margin-bottom: 14px;
}
.hero h1 { color: #ffffff; font-size: 2.05rem; font-weight: 800; margin: 0 0 8px 0; }
.hero p { color: #c2cee8; font-size: 1rem; margin: 0; max-width: 720px; line-height: 1.55; }

/* ---- tabs ---- */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px; background: #ffffff; padding: 7px; border-radius: 16px;
    border: 1px solid #e6eaf2; box-shadow: 0 6px 18px -12px rgba(15,40,80,0.25);
}
.stTabs [data-baseweb="tab"] {
    height: auto; padding: 10px 18px; border-radius: 11px;
    font-weight: 600; color: #475569; background: transparent;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(120deg, #4f46e5, #2563eb) !important;
    color: #ffffff !important; box-shadow: 0 8px 18px -8px rgba(79,70,229,0.6);
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* ---- buttons ---- */
.stButton > button {
    border-radius: 12px; font-weight: 700; padding: 0.6rem 1.2rem;
    border: 1px solid #e2e8f0; transition: all .18s ease;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(120deg, #4f46e5, #2563eb); border: none; color: #fff;
    box-shadow: 0 12px 24px -10px rgba(79,70,229,0.65);
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px); box-shadow: 0 16px 30px -10px rgba(79,70,229,0.7);
}
.stDownloadButton > button {
    border-radius: 12px; font-weight: 700; border: 1px solid #c7d2fe;
    background: #eef2ff; color: #3730a3;
}
.stDownloadButton > button:hover { background: #e0e7ff; border-color: #a5b4fc; }

/* ---- inputs & uploaders ---- */
.stTextInput input {
    border-radius: 11px !important; border: 1px solid #e2e8f0 !important; padding: 0.55rem 0.8rem !important;
}
.stTextInput input:focus { border-color: #818cf8 !important; box-shadow: 0 0 0 3px rgba(129,140,248,0.18) !important; }
[data-testid="stFileUploader"] section {
    border: 1.5px dashed #c7d0e0; border-radius: 14px; background: #fbfcff; transition: all .18s ease;
}
[data-testid="stFileUploader"] section:hover { border-color: #818cf8; background: #f5f7ff; }

/* ---- expander ---- */
[data-testid="stExpander"] {
    border: 1px solid #e6eaf2 !important; border-radius: 14px !important;
    box-shadow: 0 6px 18px -14px rgba(15,40,80,0.3); overflow: hidden; background:#fff;
}
[data-testid="stExpander"] summary { font-weight: 600; }

/* ---- bordered containers act as cards ---- */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
}

/* ---- section label ---- */
.section-label {
    display:flex; align-items:center; gap:10px;
    font-size: 1.05rem; font-weight: 700; color:#0f172a; margin: 2px 0 12px 0;
}
.section-label .dot {
    width: 30px; height: 30px; border-radius: 9px; display:grid; place-items:center;
    background: linear-gradient(120deg,#eef2ff,#e0e7ff); font-size: 15px;
}

/* ---- verdict banner ---- */
.verdict {
    display:flex; align-items:center; gap:18px;
    border-radius: 18px; padding: 20px 24px; margin: 6px 0 16px 0;
    border: 1px solid; position: relative; overflow:hidden;
}
.verdict .vicon {
    width: 52px; height: 52px; border-radius: 14px; flex: 0 0 52px;
    display:grid; place-items:center; font-size: 26px; color:#fff;
}
.verdict .vtitle { font-size: 1.25rem; font-weight: 800; line-height:1.2; margin:0; }
.verdict .vsub { font-size: 0.9rem; margin: 3px 0 0 0; opacity: 0.85; }
.verdict.pass { background: linear-gradient(115deg,#ecfdf5,#d1fae5); border-color:#a7f3d0; color:#065f46; }
.verdict.pass .vicon { background: linear-gradient(135deg,#10b981,#059669); }
.verdict.fail { background: linear-gradient(115deg,#fef2f2,#fee2e2); border-color:#fecaca; color:#991b1b; }
.verdict.fail .vicon { background: linear-gradient(135deg,#ef4444,#dc2626); }

/* ---- sub-verdict pills ---- */
.pillrow { display:flex; gap:14px; margin-bottom: 8px; }
.pill {
    flex:1; border-radius: 14px; padding: 14px 18px; border:1px solid;
    display:flex; align-items:center; justify-content:space-between; font-weight:700;
}
.pill .plabel { font-size:0.78rem; letter-spacing:0.06em; text-transform:uppercase; opacity:0.7; font-weight:700; }
.pill .pval { font-size:1.05rem; }
.pill.ok { background:#ecfdf5; border-color:#a7f3d0; color:#065f46; }
.pill.bad { background:#fef2f2; border-color:#fecaca; color:#991b1b; }

/* ---- meta strip ---- */
.metastrip {
    display:flex; flex-wrap:wrap; gap:10px; margin: 4px 0 14px 0;
}
.metachip {
    background:#fff; border:1px solid #e6eaf2; border-radius: 11px;
    padding: 9px 14px; font-size: 0.86rem; color:#334155;
    box-shadow: 0 4px 12px -10px rgba(15,40,80,0.3);
}
.metachip b { color:#0f172a; }
.metachip .k { color:#94a3b8; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.05em; display:block; margin-bottom:2px; font-weight:700; }

/* ---- field table ---- */
.ftable-wrap { overflow-x:auto; border-radius:14px; border:1px solid #e6eaf2; box-shadow:0 10px 26px -20px rgba(15,40,80,0.4); }
table.ftable { width:100%; border-collapse:collapse; font-size:0.9rem; background:#fff; }
table.ftable thead th {
    background:#0f2850; color:#fff; text-align:left; padding:12px 16px; font-weight:600; font-size:0.8rem;
    letter-spacing:0.03em; text-transform:uppercase;
}
table.ftable tbody td { padding:13px 16px; border-bottom:1px solid #eef1f6; color:#334155; vertical-align:middle; }
table.ftable tbody tr:last-child td { border-bottom:none; }
table.ftable tbody tr:nth-child(even) { background:#fafbfe; }
table.ftable .mono { font-family:'SFMono-Regular',Consolas,monospace; font-weight:600; color:#0f172a; }
table.ftable .note { color:#64748b; font-size:0.82rem; }
.badge {
    display:inline-block; padding:4px 11px; border-radius:999px; font-size:0.74rem; font-weight:700;
    white-space:nowrap;
}
.badge.ok { background:#d1fae5; color:#065f46; }
.badge.bad { background:#fee2e2; color:#991b1b; }
.badge.warn { background:#fef3c7; color:#92400e; }

/* ---- report card ---- */
.report-card h1, .report-card h2, .report-card h3 { letter-spacing:-0.01em; }

/* ---- footer note ---- */
.foot { text-align:center; color:#94a3b8; font-size:0.8rem; margin-top:28px; }
</style>
"""


def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, badge: str = "AI-POWERED VERIFICATION"):
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-badge">{html.escape(badge)}</div>
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_label(icon: str, text: str):
    st.markdown(
        f'<div class="section-label"><span class="dot">{icon}</span>{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def verdict_banner(passed: bool, title: str, subtitle: str = ""):
    kind = "pass" if passed else "fail"
    icon = "✓" if passed else "✕"
    sub = f'<p class="vsub">{html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="verdict {kind}">
            <div class="vicon">{icon}</div>
            <div>
                <p class="vtitle">{html.escape(title)}</p>
                {sub}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sub_verdict_pills(kyc_ok: bool, sheet_ok: bool,
                      kyc_label: str, sheet_label: str):
    k_cls = "ok" if kyc_ok else "bad"
    s_cls = "ok" if sheet_ok else "bad"
    st.markdown(
        f"""
        <div class="pillrow">
            <div class="pill {k_cls}">
                <span class="plabel">Part 1 · Identity (KYC)</span>
                <span class="pval">{html.escape(kyc_label)}</span>
            </div>
            <div class="pill {s_cls}">
                <span class="plabel">Part 2 · Sheet Audit</span>
                <span class="pval">{html.escape(sheet_label)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def meta_strip(items: list):
    """items: list of (label, value) tuples."""
    chips = ""
    for label, value in items:
        chips += (
            f'<div class="metachip"><span class="k">{html.escape(str(label))}</span>'
            f'<b>{html.escape(str(value))}</b></div>'
        )
    st.markdown(f'<div class="metastrip">{chips}</div>', unsafe_allow_html=True)


# ── Field table ────────────────────────────────────────────────────────────────
_STATUS_META = {
    "MATCH":                ("ok",   "MATCH"),
    "MISMATCH":             ("bad",  "MISMATCH"),
    "INTERNAL_DISCREPANCY": ("bad",  "DISCREPANCY"),
    "SCHEMA_CAVEAT":        ("warn", "CAVEAT"),
    "NOT_FOUND_IN_AFS":     ("warn", "NOT IN AFS"),
    "NOT_FOUND_IN_SHEET":   ("warn", "NOT IN SHEET"),
}


def _badge_html(status: str) -> str:
    cls, label = _STATUS_META.get(status, ("warn", status))
    return f'<span class="badge {cls}">{html.escape(label)}</span>'


def _as_dict(f):
    if isinstance(f, dict):
        return f
    return {
        "field_name": f.field_name, "status": f.status,
        "afs_distinct_values": f.afs_distinct_values,
        "sheet_raw": f.sheet_raw, "afs_normalized": f.afs_normalized,
        "sheet_normalized": f.sheet_normalized, "detail": f.detail,
    }


def field_table(fields):
    """Renders a clean, simple field comparison table from FieldResult objects or dicts."""
    rows = ""
    for f in fields:
        d = _as_dict(f)
        afs_val = d.get("afs_normalized") or " | ".join(str(v) for v in d.get("afs_distinct_values", [])) or "—"
        sheet_val = d.get("sheet_normalized") or d.get("sheet_raw") or "—"
        note = d.get("detail") or ""
        rows += (
            "<tr>"
            f"<td>{_badge_html(d.get('status',''))}</td>"
            f"<td><b>{html.escape(str(d.get('field_name','')))}</b></td>"
            f"<td class='mono'>{html.escape(str(afs_val))}</td>"
            f"<td class='mono'>{html.escape(str(sheet_val))}</td>"
            f"<td class='note'>{html.escape(str(note))}</td>"
            "</tr>"
        )
    st.markdown(
        f"""
        <div class="ftable-wrap">
          <table class="ftable">
            <thead><tr>
              <th>Status</th><th>Field</th><th>AFS Value</th><th>Sheet Value</th><th>Notes</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer():
    st.markdown(
        '<div class="foot">🔒 Confidential · Auto-generated by the KYC Verification Agent</div>',
        unsafe_allow_html=True,
    )
