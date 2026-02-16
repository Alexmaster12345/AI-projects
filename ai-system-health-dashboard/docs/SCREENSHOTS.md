# ASHD Screenshot Documentation

This document explains how to generate and manage screenshots for the ASHD dashboard documentation.

## Overview

The screenshot system automatically captures screenshots of all major dashboard features for documentation purposes. All screenshots are generated locally and should not be committed to GitHub.

## Quick Start

### Automated Setup (Recommended)

```bash
# This script handles everything: dependency check, server check, and screenshot capture
./scripts/setup_screenshots.sh
```

### Manual Process

1. **Install Dependencies**
   ```bash
   pip install selenium pillow requests
   ```

2. **Install Chrome/Chromium**
   - Ubuntu/Debian: `sudo apt-get install chromium-browser`
   - CentOS/RHEL: `sudo yum install chromium`
   - macOS: `brew install --cask google-chrome`

3. **Start ASHD Server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Run Screenshot Script**
   ```bash
   python scripts/take_screenshots.py
   ```

## Environment Variables

Optional environment variables to customize the screenshot process:

```bash
export ASHD_URL="http://localhost:8000"     # Server URL
export ASHD_USER="admin"                    # Username for login
export ASHD_PASS="admin123"                 # Password for login
```

## Screenshots Captured

The script captures the following pages/features:

| # | Screenshot | Description |
|---|------------|-------------|
| 01 | `01_login.png` | Login page |
| 02 | `02_dashboard.png` | Main dashboard with metrics |
| 03 | `03_hosts.png` | Hosts management page |
| 04 | `04_maps.png` | Network maps visualization |
| 05 | `05_inventory.png` | Inventory management |
| 06 | `06_overview.png` | Overview page |
| 07 | `07_configuration.png` | Configuration settings |
| 08 | `08_host_details.png` | Individual host details |
| 09 | `09_users.png` | **NEW**: Users management |
| 10 | `10_user_groups.png` | **NEW**: User groups management |
| 11 | `11_add_user_modal.png` | **NEW**: Add user modal dialog |
| 12 | `12_add_group_modal.png` | **NEW**: Add user group modal dialog |

## Viewing Screenshots

- **Gallery View**: Open `docs/index.html` in your browser
- **Direct Access**: Screenshots are located in `docs/screenshots/`
- **Local Only**: Screenshots are generated locally and not stored in GitHub

## Management Scripts

### Setup Script
```bash
./scripts/setup_screenshots.sh
```
- Checks for Chrome/Chromium
- Installs Python dependencies
- Verifies server is running
- Captures all screenshots

### Clean Script
```bash
./scripts/clean_screenshots.sh
```
- Removes all generated PNG files
- Preserves directory structure
- Useful before regenerating screenshots

### Direct Script
```bash
python scripts/take_screenshots.py
```
- Core screenshot capture logic
- Can be run with custom environment variables

## Technical Details

### Browser Automation
- Uses Selenium WebDriver with Chrome
- Headless mode for server environments
- Window size: 1920x1080
- Optimizes PNG files after capture

### Login Process
- Automatically logs in with provided credentials
- Handles session management
- Captures login page separately (requires logout)

### Error Handling
- Validates server connectivity before starting
- Checks for required elements before capturing
- Provides clear error messages for troubleshooting

## Troubleshooting

### Common Issues

1. **Chrome/Chromium not found**
   ```
   ❌ Chrome/Chromium not found. Please install it first
   ```
   **Solution**: Install Chrome or Chromium browser

2. **Server not running**
   ```
   ❌ ASHD server is not running on http://localhost:8000
   ```
   **Solution**: Start the ASHD server with `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

3. **Login failed**
   ```
   ❌ Login failed
   ```
   **Solution**: Verify credentials and ensure admin user exists

4. **Missing dependencies**
   ```
   ❌ Missing Python dependencies
   ```
   **Solution**: Run `pip install selenium pillow requests`

### Debug Mode

For debugging, you can modify the script to disable headless mode:

```python
# In take_screenshots.py, comment out this line:
chrome_options.add_argument('--headless')
```

## Git Integration

- Screenshots are ignored by `.gitignore`
- Only the directory structure is tracked (via `.gitkeep`)
- This ensures screenshots are generated locally by each developer
- Reduces repository size and avoids outdated screenshots

## Contributing

When adding new features to the dashboard:

1. Update `scripts/take_screenshots.py` to capture new pages
2. Update `docs/index.html` to display new screenshots
3. Update this documentation (`docs/SCREENSHOTS.md`)
4. Update the screenshots table in this file

## Automation

For CI/CD integration, you can:

1. Set up a headless Chrome environment
2. Run the screenshot script as part of the build process
3. Store screenshots in artifact storage
4. Use screenshots for visual regression testing
