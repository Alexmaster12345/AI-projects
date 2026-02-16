#!/usr/bin/env python3
"""
Automated screenshot generator for ASHD dashboard.
Captures screenshots of all major pages and features.
"""

import os
import sys
import time
import asyncio
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from PIL import Image
import requests

# Configuration
BASE_URL = os.getenv('ASHD_URL', 'http://localhost:8000')
USERNAME = os.getenv('ASHD_USER', 'admin')
PASSWORD = os.getenv('ASHD_PASS', 'admin123')
SCREENSHOTS_DIR = Path(__file__).parent.parent / 'docs' / 'screenshots'
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

def setup_driver():
    """Setup Chrome WebDriver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}')
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)
    return driver

def login(driver):
    """Login to the dashboard."""
    print("Logging in...")
    driver.get(f"{BASE_URL}/login")
    
    # Wait for login form
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "username"))
    )
    
    # Fill credentials
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    
    # Wait for dashboard to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "appShell"))
    )
    print("Login successful!")

def take_screenshot(driver, filename, description, wait_for=None, scroll=True):
    """Take a screenshot of the current page."""
    print(f"Capturing: {description}")
    
    if wait_for:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(wait_for)
        )
    
    # Wait a bit for any animations
    time.sleep(2)
    
    # Scroll to top if requested
    if scroll:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
    
    # Take screenshot
    filepath = SCREENSHOTS_DIR / filename
    driver.save_screenshot(str(filepath))
    
    # Optimize the image
    with Image.open(filepath) as img:
        img.save(filepath, 'PNG', optimize=True)
    
    print(f"Saved: {filepath}")

def main():
    """Main screenshot capture workflow."""
    print("Starting ASHD screenshot capture...")
    
    # Ensure screenshots directory exists
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"Server returned status {response.status_code}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Cannot connect to server at {BASE_URL}: {e}")
        print("Please ensure the ASHD server is running.")
        sys.exit(1)
    
    driver = setup_driver()
    
    try:
        # Login first
        login(driver)
        
        # 01. Login page (need to logout first)
        driver.get(f"{BASE_URL}/logout")
        time.sleep(1)
        take_screenshot(driver, "01_login.png", "Login page", 
                       wait_for=(By.NAME, "username"))
        
        # Login again for subsequent screenshots
        login(driver)
        
        # 02. Dashboard
        take_screenshot(driver, "02_dashboard.png", "Dashboard",
                       wait_for=(By.ID, "appShell"))
        
        # 03. Hosts
        driver.get(f"{BASE_URL}/#hosts")
        take_screenshot(driver, "03_hosts.png", "Hosts page",
                       wait_for=(By.ID, "hostsTable"))
        
        # 04. Maps
        driver.get(f"{BASE_URL}/#maps")
        take_screenshot(driver, "04_maps.png", "Network maps",
                       wait_for=(By.ID, "mapsContainer"))
        
        # 05. Inventory
        driver.get(f"{BASE_URL}/#inventory")
        take_screenshot(driver, "05_inventory.png", "Inventory",
                       wait_for=(By.ID, "inventoryTable"))
        
        # 06. Overview
        driver.get(f"{BASE_URL}/overview")
        take_screenshot(driver, "06_overview.png", "Overview",
                       wait_for=(By.ID, "overviewContainer"))
        
        # 07. Configuration
        driver.get(f"{BASE_URL}/configuration")
        take_screenshot(driver, "07_configuration.png", "Configuration",
                       wait_for=(By.ID, "configContainer"))
        
        # 08. Host details (need to create a host first or use existing)
        # Try to navigate to first host if available
        try:
            driver.get(f"{BASE_URL}/")
            # Wait for hosts to load
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-action='hosts']"))
            )
            # Click on first host if available
            host_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/host/']")
            if host_links:
                host_links[0].click()
                take_screenshot(driver, "08_host_details.png", "Host details",
                               wait_for=(By.ID, "hostContainer"))
            else:
                print("No hosts found, skipping host details screenshot")
        except Exception as e:
            print(f"Could not capture host details: {e}")
        
        # 09. Users page (new feature)
        driver.get(f"{BASE_URL}/users")
        take_screenshot(driver, "09_users.png", "Users management",
                       wait_for=(By.ID, "usersTable"))
        
        # 10. User groups page (new feature)
        driver.get(f"{BASE_URL}/user-groups")
        take_screenshot(driver, "10_user_groups.png", "User groups management",
                       wait_for=(By.ID, "userGroupsTable"))
        
        # 11. Add user modal (open modal)
        driver.get(f"{BASE_URL}/users")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "addUserBtn"))
        )
        driver.find_element(By.ID, "addUserBtn").click()
        take_screenshot(driver, "11_add_user_modal.png", "Add user modal",
                       wait_for=(By.ID, "userModal"))
        
        # 12. Add user group modal
        driver.get(f"{BASE_URL}/user-groups")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "addGroupBtn"))
        )
        driver.find_element(By.ID, "addGroupBtn").click()
        take_screenshot(driver, "12_add_group_modal.png", "Add user group modal",
                       wait_for=(By.ID, "groupModal"))
        
        print("\n✅ All screenshots captured successfully!")
        print(f"📁 Screenshots saved to: {SCREENSHOTS_DIR}")
        
    except Exception as e:
        print(f"❌ Error capturing screenshots: {e}")
        sys.exit(1)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
