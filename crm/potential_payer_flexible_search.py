"""Utility functions for flexible potential payer search."""

from __future__ import annotations

import sqlalchemy

from db import database, PotentialPayer


async def search_potential_payers(query: str) -> list[sqlalchemy.Row]:
    """Search potential payers by ID or part of full name."""
    text = query.strip()
    if not text:
        return []
    if text.isdigit():
        row = await database.fetch_one(
            sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == int(text))
        )
        return [row] if row else []
    pattern = f"%{text}%"
    rows = await database.fetch_all(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.full_name.ilike(pattern))
    )
    return rows
