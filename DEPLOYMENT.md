# Deployment Guide — Streamlit Cloud + Neon Postgres

This deploys the app for free with a **dedicated PostgreSQL database** (Neon) so your
verification history survives restarts. Follow the steps in order.

---

## ⚠️ STEP 0 — Rotate your leaked secrets FIRST (do not skip)

Your Google service account key (`AFS_Verification_GS.json`), OpenAI key, and Gmail
app password were exposed (the key was committed to git; the others were shown in plain
text). Anything exposed must be replaced before going public.

1. **Google service account key**
   - Go to <https://console.cloud.google.com/> → IAM & Admin → **Service Accounts**.
   - Open `afs-verification@…iam.gserviceaccount.com` → **Keys** tab.
   - **Delete** the old key, then **Add Key → Create new key → JSON**. Download it.
   - Re-share your Google Sheet with the service account's `client_email` (it stays the same).
2. **OpenAI key** — <https://platform.openai.com/api-keys> → revoke the old key, create a new one.
3. **Gmail app password** — <https://myaccount.google.com/apppasswords> → delete the old one, generate a new 16-char password.

Use the **new** values everywhere below. The old `AFS_Verification_GS.json` file has
already been removed from git tracking and added to `.gitignore`.

---

## STEP 1 — Create the Neon database (5 min)

1. Sign up at <https://neon.tech> (free tier, no credit card).
2. **Create Project** → pick a region close to you → Create.
3. On the project dashboard, find **Connection string** (a.k.a. "Connection Details").
   Copy the **URI** that looks like:
   ```
   postgresql://alex:AbC123@ep-cool-name-12345.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. Save it — this is your `DATABASE_URL`. The app creates its tables automatically on
   first run, so there is nothing to set up inside Neon.

---

## STEP 2 — Push the code to GitHub (10 min)

> If you've never used GitHub: install **GitHub Desktop** (<https://desktop.github.com>)
> for a click-based flow, or use the terminal commands below.

1. Create a new repository at <https://github.com/new> (set it **Private**).
2. In the project folder, run:
   ```bash
   pip install -r requirements-dev.txt
   pytest
   git add .
   git commit -m "Prepare for deployment"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
3. **Verify no secrets were pushed.** On GitHub, confirm these files are **NOT** present:
   - `AFS_Verification_GS.json` ❌ (must be absent)
   - `.env` ❌ (must be absent)
   - `.streamlit/secrets.toml` ❌ (must be absent)

   These should be present: `app.py`, `requirements.txt`, `runtime.txt`, `.gitignore`,
   `.streamlit/secrets.toml.example`, `tests/fixtures/afs_313_extraction.json` ✅

---

## STEP 3 — Deploy on Streamlit Community Cloud (5 min)

1. Go to <https://share.streamlit.io> and sign in **with GitHub**.
2. **Create app** → **Deploy a public app from a repo** → choose your repo,
   branch `main`, main file `app.py`.
3. Before clicking Deploy, open **Advanced settings → Secrets** and paste the contents
   below (this is the cloud equivalent of your `.env`). Use the template in
   `.streamlit/secrets.toml.example` as your guide:
   ```toml
   OPENAI_API_KEY = "sk-...new-key..."
   SMTP_EMAIL = "you@gmail.com"
   SMTP_PASSWORD = "new-16-char-app-password"
   DATABASE_URL = "postgresql://USER:PASS@HOST/neondb?sslmode=require"
   DEFAULT_SHEET_ID = "1pdRt04-OgUvEQJLXqZXBtZJO2Cs7Yg4KwfmW7k7heYg"

   GOOGLE_SHEETS_CREDENTIALS_JSON = '''
   { ...paste the ENTIRE new service-account JSON file here... }
   '''
   ```
   > The triple single-quotes `'''` around the JSON are required so the embedded
   > quotes and `\n` line breaks in the private key are preserved.
4. Click **Deploy**. First build takes a few minutes (installing dependencies).
5. When it's live you get a URL like `https://<your-app>.streamlit.app`.

---

## STEP 4 — Keep it private (single user, for now)

You chose "just me for now". Streamlit Community Cloud apps are public-by-URL by default.
Two easy options:

- **Easiest:** in the Streamlit Cloud app settings → **Sharing**, restrict viewers to
  your Google account / invited emails only.
- **Or** add a simple password gate in code later (`st.text_input(type="password")`
  checked against a `APP_PASSWORD` secret). Ask me and I'll wire it in.

Because KYC documents are sensitive personal data, do **not** make the app fully public.

---

## How secrets resolve (so you understand it)

| Variable | Local (`.env`) | Cloud (Streamlit Secrets) | Used by |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | ✅ | agent.py |
| `SMTP_EMAIL` / `SMTP_PASSWORD` | ✅ | ✅ | notifier.py |
| `DATABASE_URL` | *(unset → SQLite file)* | ✅ Neon Postgres | database.py |
| `GOOGLE_SHEETS_CREDENTIALS_PATH` | ✅ file path | — | sheets.py (local) |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | — | ✅ JSON content | sheets.py (cloud) |
| `DEFAULT_SHEET_ID` | ✅ | ✅ | app.py |

- **Locally**: nothing changes. No `DATABASE_URL` → it uses the SQLite file as before;
  `python-dotenv` loads `.env`; Google creds load from the file path.
- **In the cloud**: `app.py` copies `st.secrets` into environment variables on startup,
  so the same code reads them transparently. `DATABASE_URL` present → it uses Neon Postgres;
  `GOOGLE_SHEETS_CREDENTIALS_JSON` present → it builds Google creds from that string.

---

## Updating the app later

Just `git push` to `main`. Streamlit Cloud auto-redeploys on every push. To change a
secret, edit it in the Streamlit Cloud dashboard (Settings → Secrets) — no redeploy needed.

---

## Troubleshooting

- **`No module named psycopg2`** → make sure `requirements.txt` (with `psycopg2-binary`
  and `sqlalchemy`) was pushed.
- **DB connection errors** → confirm `DATABASE_URL` ends with `?sslmode=require` and has
  no surrounding quotes inside the value.
- **Google "invalid_grant" / permission errors** → re-share the Sheet with the service
  account `client_email`, and confirm the JSON in secrets is the **new** rotated key.
- **App sleeps / slow first load** → normal on the free tier; it wakes on visit.
