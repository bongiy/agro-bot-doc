import asyncio
from datetime import datetime, timedelta
import sqlalchemy
from telegram.ext import Application
from db import database, CRMEvent, User, Payer, PotentialPayer, Contract, LandPlot


async def _get_entity_name(row) -> str:
    if row["entity_type"] == "payer":
        p = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == row["entity_id"]))
        return p["name"] if p else f"ID {row['entity_id']}"
    if row["entity_type"] == "potential_payer":
        p = await database.fetch_one(sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == row["entity_id"]))
        return p["full_name"] if p else f"ID {row['entity_id']}"
    if row["entity_type"] == "contract":
        c = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == row["entity_id"]))
        return f"\u0414\u043E\u0433\u043E\u0432\u0456\u0440 \u2116{c['number']}" if c else f"ID {row['entity_id']}"
    land = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == row["entity_id"]))
    return land["cadaster"] if land else f"ID {row['entity_id']}"


async def _format_reminder(row, header: str) -> str:
    entity = await _get_entity_name(row)
    dt = row["event_datetime"].strftime("%d.%m.%Y \u043E %H:%M")
    comment = row["comment"] or "-"
    return f"{header}\n\U0001F4C5 {dt}\n{row['event_type']} {entity}\n\U0001F4DD \u041A\u043E\u043C\u0435\u043D\u0442\u0430\u0440: {comment}"


async def _admin_ids() -> list[int]:
    rows = await database.fetch_all(User.select().where(User.c.role == "admin", User.c.is_active == True))
    return [r["telegram_id"] for r in rows]


async def _send_to(recipients: set[int], text: str, app: Application):
    for uid in recipients:
        try:
            await app.bot.send_message(uid, text)
        except Exception:
            pass


async def _update_status(event_id: int, status_key: str, status: dict):
    status[status_key] = True
    await database.execute(
        CRMEvent.update().where(CRMEvent.c.id == event_id).values(reminder_status=status)
    )


async def check_daily(app: Application):
    today = datetime.now().date()
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent).where(
            sqlalchemy.func.date(CRMEvent.c.event_datetime) == today,
            CRMEvent.c.status == "planned",
        )
    )
    if not rows:
        return
    admin_ids = await _admin_ids()
    for r in rows:
        status = r["reminder_status"] or {}
        if status.get("daily"):
            continue
        text = await _format_reminder(r, "\u23F0 \u041F\u043E\u0434\u0456\u044F \u0441\u044C\u043E\u0433\u043E\u0434\u043D\u0456:")
        recipients = set(admin_ids)
        recipients.add(r["created_by_user_id"])
        await _send_to(recipients, text, app)
        await _update_status(r["id"], "daily", status)


async def check_one_hour(app: Application):
    now = datetime.now()
    start = now + timedelta(hours=1) - timedelta(minutes=15)
    end = now + timedelta(hours=1) + timedelta(minutes=15)
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent).where(
            CRMEvent.c.event_datetime >= start,
            CRMEvent.c.event_datetime <= end,
            CRMEvent.c.status == "planned",
        )
    )
    if not rows:
        return
    admin_ids = await _admin_ids()
    for r in rows:
        status = r["reminder_status"] or {}
        if status.get("1h"):
            continue
        text = await _format_reminder(r, "\u23F0 \u041F\u043E\u0434\u0456\u044F \u0437\u0430 \u0433\u043E\u0434\u0438\u043D\u0443:")
        recipients = set(admin_ids)
        recipients.add(r["created_by_user_id"])
        await _send_to(recipients, text, app)
        await _update_status(r["id"], "1h", status)


async def check_now(app: Application):
    now = datetime.now()
    start = now - timedelta(minutes=5)
    end = now + timedelta(minutes=5)
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent).where(
            CRMEvent.c.event_datetime >= start,
            CRMEvent.c.event_datetime <= end,
            CRMEvent.c.status == "planned",
        )
    )
    if not rows:
        return
    admin_ids = await _admin_ids()
    for r in rows:
        status = r["reminder_status"] or {}
        if status.get("now"):
            continue
        text = await _format_reminder(r, "\u23F0 \u041F\u043E\u0434\u0456\u044F \u0437\u0430\u0440\u0430\u0437:")
        recipients = set(admin_ids)
        recipients.add(r["created_by_user_id"])
        await _send_to(recipients, text, app)
        await _update_status(r["id"], "now", status)


def _seconds_until(hour: int, minute: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


a_sync_tasks = []

def start_reminder_tasks(app: Application):
    loop = asyncio.get_event_loop()
    a_sync_tasks.append(loop.create_task(_daily_loop(app)))
    a_sync_tasks.append(loop.create_task(_one_hour_loop(app)))
    a_sync_tasks.append(loop.create_task(_now_loop(app)))


async def stop_reminder_tasks():
    for t in a_sync_tasks:
        t.cancel()
    if a_sync_tasks:
        await asyncio.gather(*a_sync_tasks, return_exceptions=True)
    a_sync_tasks.clear()


async def _daily_loop(app: Application):
    while True:
        await asyncio.sleep(_seconds_until(9, 0))
        await check_daily(app)


async def _one_hour_loop(app: Application):
    while True:
        await check_one_hour(app)
        await asyncio.sleep(15 * 60)


async def _now_loop(app: Application):
    while True:
        await check_now(app)
        await asyncio.sleep(5 * 60)

