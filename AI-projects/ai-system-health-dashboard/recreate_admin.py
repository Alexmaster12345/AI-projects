#!/usr/bin/env python3
"""Recreate admin user with proper password hash."""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.auth_storage import auth_storage, init_auth_storage

async def recreate_admin():
    """Recreate admin user with proper password hash."""
    await init_auth_storage()
    
    if not auth_storage.enabled:
        print("❌ Auth storage is disabled")
        return
    
    # Delete existing admin user if it exists
    existing_user = auth_storage.get_user_by_username("admin")
    if existing_user:
        try:
            # Delete the user directly from the database
            conn = auth_storage._require_conn()
            with auth_storage._lock:
                conn.execute("DELETE FROM users WHERE username = ?", ("admin",))
                conn.commit()
            print("🗑️  Deleted existing admin user")
        except Exception as e:
            print(f"❌ Failed to delete existing user: {e}")
            return
    
    # Create admin user with proper password hash
    try:
        user = auth_storage.create_user(
            username="admin",
            password="admin123",  # Change this in production!
            role="admin",
            email="admin@localhost"
        )
        print(f"✅ Created admin user with ID: {user.id}")
        print("🔑 Login credentials:")
        print("   Username: admin")
        print("   Password: admin123")
        print("⚠️  Remember to change the password in production!")
        
        # Test password verification
        is_valid = auth_storage.verify_password("admin123", user.password_hash)
        print(f"✅ Password verification test: {is_valid}")
        
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")

if __name__ == "__main__":
    asyncio.run(recreate_admin())
