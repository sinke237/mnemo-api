"""Bootstrap script to create an admin user and API key.

Usage:
    source venv/bin/activate
    python scripts/bootstrap_admin.py

The script prints the plaintext API key once; save it immediately.
"""

import asyncio

from mnemo.db.database import AsyncSessionLocal
from mnemo.models.user import User
from mnemo.services.api_key import create_api_key
from mnemo.utils.id_generator import generate_user_id
from mnemo.core.constants import PermissionScope


async def create_admin_user():
    async with AsyncSessionLocal() as db:
        # Create admin user
        user = User(
            id=generate_user_id(),
            display_name="Admin User",
            country="CM",
            timezone="Africa/Douala",
            preferred_language="en",
            daily_goal_cards=20,
        )
        db.add(user)
        await db.flush()

        # Create admin API key
        api_key_record, plain_key = await create_api_key(
            db=db,
            user_id=user.id,
            name="Admin Key",
            is_live=True,
            scopes=[PermissionScope.ADMIN],
        )

        await db.commit()

        print(f"✅ Admin user created: {user.id}")
        print(f"🔑 API Key (SAVE THIS): {plain_key}")
        print(f"   Hint: ...{api_key_record.key_hint}")


if __name__ == "__main__":
    asyncio.run(create_admin_user())
