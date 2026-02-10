# VectorPass

A small Bootstrap-based web vault for storing per-site usernames and passwords.

## Features
- Multi-user accounts (register/login)
- Vault unlock (requires password) with auto-lock after inactivity
- Credentials encrypted at rest (AES-GCM) with key derived from your password (Argon2id)

## Quickstart
1) Create and edit `.env` (see `.env.example`).
2) Install dependencies: `pip install -r requirements.txt`
3) Run: `uvicorn app.main:app --reload --port 8001`
4) Open: http://127.0.0.1:8001

## Chrome extension (Autofill)
This repo includes a simple Chrome extension in `chrome-extension/`.

1) In VectorPass (as admin/operator): Vault → **Tokens** → create a token
2) In Chrome: open `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select `VectorPass/chrome-extension/`
3) In the extension **Options**, set:
	- Base URL: `http://127.0.0.1:8001`
	- API Token: (paste the token you created)
4) On a login page, click the extension → **Find & Autofill**

## Notes
- The vault unlock key is stored only in server memory (per session) and is cleared on server restart.
- For production, run behind HTTPS and set cookie security env vars accordingly.
