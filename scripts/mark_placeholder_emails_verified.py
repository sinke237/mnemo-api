"""Admin script: mark email_placeholder entries as verified.

Usage examples:

# Mark specific users by id
python -m scripts.mark_placeholder_emails_verified --ids usr_abc,usr_def

# Mark specific placeholder emails
python -m scripts.mark_placeholder_emails_verified --emails user_usr_abc@placeholder.mnemo.local

# Mark all placeholder emails (destructive) - must pass --confirm
python -m scripts.mark_placeholder_emails_verified --all --confirm
"""
from __future__ import annotations

import asyncio
import argparse
import logging
from typing import list

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.db.database import AsyncSessionLocal
from mnemo.models.user import User

logger = logging.getLogger("mark_placeholder_emails_verified")
logging.basicConfig(level=logging.INFO)


async def mark_by_ids(session: AsyncSession, ids: list[str]) -> int:
    stmt = (
        sa.update(User)
        .where(User.id.in_(ids), User.email_placeholder.isnot(None))
        .values(email_verified=True, email_verified_at=sa.func.now())
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def mark_by_emails(session: AsyncSession, emails: list[str]) -> int:
    # Match against email_placeholder or normalized_email_placeholder (case-insensitive)
    lowered = [e.strip().lower() for e in emails]
    stmt = (
        sa.update(User)
        .where(sa.func.lower(User.email_placeholder).in_(lowered))
        .values(email_verified=True, email_verified_at=sa.func.now())
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def mark_all_placeholders(session: AsyncSession) -> int:
    stmt = (
        sa.update(User)
        .where(User.email_placeholder.isnot(None))
        .values(email_verified=True, email_verified_at=sa.func.now())
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mark placeholder emails as verified")
    parser.add_argument("--ids", help="Comma-separated list of user ids to mark verified")
    parser.add_argument(
        "--emails", help="Comma-separated list of placeholder emails to mark verified"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Mark ALL rows with non-null email_placeholder as verified (requires --confirm)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required to confirm destructive operations such as --all",
    )

    args = parser.parse_args(argv)

    if args.all and not args.confirm:
        logger.error("--all requires --confirm to run")
        return 2

    async with AsyncSessionLocal() as session:
        total = 0
        if args.ids:
            ids = [s.strip() for s in args.ids.split(",") if s.strip()]
            logger.info("Marking by ids", ids=ids)
            changed = await mark_by_ids(session, ids)
            logger.info("Updated rows", count=changed)
            total += changed

        if args.emails:
            emails = [s.strip() for s in args.emails.split(",") if s.strip()]
            logger.info("Marking by emails", emails=emails)
            changed = await mark_by_emails(session, emails)
            logger.info("Updated rows", count=changed)
            total += changed

        if args.all:
            logger.info("Marking all placeholder emails as verified")
            changed = await mark_all_placeholders(session)
            logger.info("Updated rows", count=changed)
            total += changed

        if total == 0:
            logger.info("No rows updated. Check inputs or placeholders present in the DB.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
