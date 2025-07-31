"""View CRM events for a specific date with pagination."""

from __future__ import annotations

from datetime import datetime
from math import ceil

import sqlalchemy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import database, CRMEvent
from utils.fsm_navigation import (
    back_cancel_keyboard,
    CANCEL_BTN,
    handle_back_cancel,
    cancel_handler,
)
from crm.events import format_event, show_menu


DATE_INPUT, SHOW_PAGE = range(2)
PAGE_SIZE = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user for date to view events."""
    await update.message.reply_text(
        "Введіть дату (ДД.ММ.РРРР):", reply_markup=back_cancel_keyboard
    )
    return DATE_INPUT


async def date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle date input and show first page."""
    result = await handle_back_cancel(update, context, show_menu)
    if result is not None:
        return result
    try:
        d = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Некоректна дата. Спробуйте ще:")
        return DATE_INPUT

    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent)
        .where(sqlalchemy.func.date(CRMEvent.c.event_datetime) == d)
        .order_by(CRMEvent.c.event_datetime.asc())
    )
    context.user_data["ev_rows"] = [dict(r) for r in rows]
    context.user_data["ev_page"] = 0
    return await _show_page(update.message, context)


async def page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle navigation buttons."""
    query = update.callback_query
    await query.answer()
    action = query.data
    page = context.user_data.get("ev_page", 0)
    rows = context.user_data.get("ev_rows", [])
    total_pages = max(1, ceil(len(rows) / PAGE_SIZE))

    if action == "prev" and page > 0:
        context.user_data["ev_page"] = page - 1
    elif action == "next" and page < total_pages - 1:
        context.user_data["ev_page"] = page + 1
    return await _show_page(query.message, context)


async def _show_page(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = context.user_data.get("ev_rows", [])
    page = context.user_data.get("ev_page", 0)
    if not rows:
        await msg.reply_text("Подій не знайдено.")
        return ConversationHandler.END

    total_pages = max(1, ceil(len(rows) / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    context.user_data["ev_page"] = page
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = rows[start:end]
    texts = [await format_event(r) for r in chunk]
    text = "\n\n".join(texts)

    if total_pages > 1:
        kb = [
            [
                InlineKeyboardButton("◀️ Назад", callback_data="prev"),
                InlineKeyboardButton(f"{page + 1} / {total_pages}", callback_data="noop"),
                InlineKeyboardButton("▶️ Далі", callback_data="next"),
            ]
        ]
        markup = InlineKeyboardMarkup(kb)
    else:
        markup = None

    if getattr(getattr(msg, "from_user", None), "is_bot", False):
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.reply_text(text, reply_markup=markup)
    return SHOW_PAGE


view_events_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📅 Події за датою$"), start)],
    states={
        DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_input)],
        SHOW_PAGE: [
            CallbackQueryHandler(page_cb, pattern="^(prev|next)$"),
            CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$")
        ],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_menu))],
)
