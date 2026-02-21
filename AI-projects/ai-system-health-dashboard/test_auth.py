#!/usr/bin/env python3
"""Test authentication."""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.auth_storage import auth_storage, init_auth_storage

async def test_auth():
    """Test authentication."""
    await init_auth_storage()
    
    if not auth_storage.enabled:
        print("❌ Auth storage is disabled")
        return
    
    # Get the admin user
    user = auth_storage.get_user_by_username("admin")
    if not user:
        print("❌ Admin user not found")
        return
    
    print(f"✅ Found user: {user.username}")
    print(f"   Role: {user.role}")
    print(f"   Active: {user.is_active}")
    
    # Test password verification
    try:
        is_valid = auth_storage.verify_password("admin123", user.password_hash)
        print(f"   Password valid: {is_valid}")
    except Exception as e:
        print(f"❌ Password verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth())
