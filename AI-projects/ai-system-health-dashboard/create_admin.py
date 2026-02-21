#!/usr/bin/env python3
"""Create default admin user for the dashboard."""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.auth_storage import auth_storage, init_auth_storage

async def create_admin():
    """Create a default admin user."""
    await init_auth_storage()
    
    if not auth_storage.enabled:
        print("❌ Auth storage is disabled")
        return
    
    # Check if admin user already exists
    existing_user = auth_storage.get_user_by_username("admin")
    if existing_user:
        print("✅ Admin user already exists")
        return
    
    # Create admin user
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
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")

if __name__ == "__main__":
    asyncio.run(create_admin())
