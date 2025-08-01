from __future__ import annotations

import sqlalchemy
from db import database, Payer, PotentialPayer, Contract, LandPlot, User

async def format_event(row) -> str:
    """Return formatted event representation for display."""
    if row["entity_type"] == "payer":
        p = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == row["entity_id"]))
        entity = f"\U0001F464 {p['name']} (поточний)" if p else f"ID {row['entity_id']}"
    elif row["entity_type"] == "potential_payer":
        p = await database.fetch_one(sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == row["entity_id"]))
        entity = f"\U0001F464 {p['full_name']} (потенційний)" if p else f"ID {row['entity_id']}"
    elif row["entity_type"] == "contract":
        c = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == row["entity_id"]))
        entity = f"\U0001F4DC Договір №{c['number']}" if c else f"ID {row['entity_id']}"
    else:
        land = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == row["entity_id"]))
        entity = f"\U0001F4CD {land['cadaster']}" if land else f"ID {row['entity_id']}"
    d = row["event_datetime"].strftime("%d.%m.%Y %H:%M")
    user = await database.fetch_one(sqlalchemy.select(User).where(User.c.telegram_id == row["responsible_user_id"]))
    resp = user["full_name"] if user else f"ID {row['responsible_user_id']}"
    txt = (
        f"\U0001F4C5 {d} — {row['event_type']}\n"
        f"{entity}\n"
        f"\U0001F9D1\u200D\U0001F4BC Відповідальний: {resp}\n"
        f"\U0001F4DD {row['comment'] or '-'}"
    )
    return txt
