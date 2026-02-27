# VectorPass Chrome Extension

Autofill and save login credentials from your VectorPass vault directly in Chrome.

## Features

- **Auto-detect** saved logins when you visit a login page — shows a fill banner
- **One-click autofill** — fills username and password into the current page's form
- **Save prompt** — when you submit a login form, a banner asks if you want to save to VectorPass
- **Manual save** — use the popup to manually save any credential
- **Popup** — click the extension icon to see a matched login or save one manually

## Installation (Developer mode)

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (toggle, top-right)
3. Click **Load unpacked**
4. Select the `chrome-extension/` folder inside this project
5. The VectorPass icon appears in your toolbar

## Setup

1. Open VectorPass in your browser and sign in
2. Go to **Vault → Tokens** (top navbar) → **Create token**, name it *Chrome extension*
3. Copy the token (shown only once)
4. Click the VectorPass extension icon → **⚙ Options**
5. Enter your VectorPass server URL (e.g. `http://192.168.50.225:8001`)
6. Paste your API token
7. Click **Save** then **Test connection** — should show ✓

## Usage

| Scenario | What happens |
|---|---|
| Visit a page with a saved login | A banner slides in: **"Fill login?"** — click to autofill |
| Submit a login form | A banner asks **"Save to VectorPass?"** — click Save |
| Click extension icon | Shows matched login + **⚡ Fill login** button, or manual save form |

## Files

| File | Purpose |
|---|---|
| `manifest.json` | Extension manifest (MV3) |
| `content.js` | Injected into every page — detects forms, shows banners |
| `background.js` | Service worker — handles API calls to VectorPass |
| `popup.html/js` | Extension popup UI |
| `options.html/js` | Settings page (URL + token) |

## API used

The extension communicates with VectorPass via two JSON endpoints authenticated with a Bearer token:

- `GET /api/ext/match?url=<page_url>` — find saved login for a URL
- `POST /api/ext/add` — save a new login to the vault
