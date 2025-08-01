# FSM rewrite for viewing CRM events
from __future__ import annotations

from datetime import datetime

import sqlalchemy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from db import database, CRMEvent
from crm.event_utils import format_event

SELECT_VIEW_MODE, SHOW_EVENTS = range(2)


async def start_event_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show event view mode selection."""
    context.user_data.clear()
    buttons = [
        [InlineKeyboardButton("1️⃣ Події на сьогодні", callback_data="view_today")],
        [InlineKeyboardButton("2️⃣ Найближчі події", callback_data="view_upcoming")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_view")],
    ]
    markup = InlineKeyboardMarkup(buttons)
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.edit_text("📆 Оберіть режим перегляду:", reply_markup=markup)
    else:
        await update.message.reply_text("📆 Оберіть режим перегляду:", reply_markup=markup)
    return SELECT_VIEW_MODE


async def get_events_today() -> list[dict]:
    today = datetime.now().date()
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent)
        .where(sqlalchemy.func.date(CRMEvent.c.event_datetime) == today)
        .order_by(CRMEvent.c.event_datetime)
        .limit(5)
    )
    return [dict(r) for r in rows]


async def get_upcoming_events() -> list[dict]:
    now = datetime.now()
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent)
        .where(CRMEvent.c.event_datetime >= now)
        .where(CRMEvent.c.status == "planned")
        .order_by(CRMEvent.c.event_datetime)
        .limit(5)
    )
    return [dict(r) for r in rows]


async def render_event_list(update: Update, events: list[dict]) -> int:
    buttons = [
        [InlineKeyboardButton("🔁 Спробувати знову", callback_data="retry_view")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_view")],
    ]
    markup = InlineKeyboardMarkup(buttons)
    query = update.callback_query
    if not events:
        text = "\U0001F4ED Подій не знайдено" if query else "\U0001F4ED Подій не знайдено"
    else:
        texts = [await format_event(r) for r in events]
        text = "\n\n".join(texts)
    if query:
        await query.message.edit_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return SHOW_EVENTS


async def view_today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    events = await get_events_today()
    return await render_event_list(update, events)


async def view_upcoming_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    events = await get_upcoming_events()
    return await render_event_list(update, events)


async def cancel_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Перегляд скасовано.", reply_markup=None)
    else:
        await update.message.reply_text("❌ Перегляд скасовано.")
    return ConversationHandler.END


async def retry_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    return await start_event_view(update, context)


view_event_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_event_view, pattern="^view_events$")],
    states={
        SELECT_VIEW_MODE: [
            CallbackQueryHandler(view_today_handler, pattern="^view_today$"),
            CallbackQueryHandler(view_upcoming_handler, pattern="^view_upcoming$"),
            CallbackQueryHandler(retry_view, pattern="^retry_view$"),
            CallbackQueryHandler(cancel_view, pattern="^cancel_view$"),
        ],
        SHOW_EVENTS: [
            CallbackQueryHandler(retry_view, pattern="^retry_view$"),
            CallbackQueryHandler(cancel_view, pattern="^cancel_view$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel_view, pattern="^cancel_view$")],
)
