from __future__ import annotations

from datetime import datetime, date
from math import ceil

import sqlalchemy
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import database, CRMEvent
from crm.event_fsm_navigation import (
    BACK_BTN,
    CANCEL_BTN,
    push_state,
    handle_back_cancel,
    cancel_handler,
    show_crm_menu,
)
from crm.event_utils import format_event


# conversation states for date filtering
FILTER_DATE_MODE, FILTER_DATES_LIST, FILTER_ALL_EVENTS = range(3)
PAGE_SIZE = 5


async def start(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user to choose filtering mode."""
    push_state(context, FILTER_DATE_MODE)
    kb = ReplyKeyboardMarkup(
        [["1️⃣ Обрати дату", "2️⃣ Всі події"], [BACK_BTN, CANCEL_BTN]],
        resize_keyboard=True,
    )
    await msg.reply_text("\U0001F4C5 Оберіть варіант:", reply_markup=kb)
    return FILTER_DATE_MODE


async def mode_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mode selection."""
    result = await handle_back_cancel(update, context, show_crm_menu)
    if result is not None:
        if result == FILTER_DATE_MODE:
            return FILTER_DATE_MODE
        return result
    text = update.message.text.strip()
    if text.startswith("1"):
        return await _show_dates(update.message, context)
    if text.startswith("2"):
        return await _show_all_start(update.message, context)
    await update.message.reply_text("Оберіть варіант з меню:")
    return FILTER_DATE_MODE


async def _show_dates(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = await database.fetch_all(
        sqlalchemy.select(sqlalchemy.func.date(CRMEvent.c.event_datetime).label("d"))
        .group_by("d")
        .order_by(sqlalchemy.func.date(CRMEvent.c.event_datetime))
    )
    dates: list[date] = [r["d"] for r in rows]
    context.user_data["dates"] = dates
    context.user_data["date_page"] = 0
    push_state(context, FILTER_DATES_LIST)
    return await _show_dates_page(msg, context)


async def _show_dates_page(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    dates: list[date] = context.user_data.get("dates", [])
    page = context.user_data.get("date_page", 0)
    if not dates:
        await msg.reply_text("Подій не знайдено.")
        return ConversationHandler.END
    per_page = 10
    total_pages = max(1, ceil(len(dates) / per_page))
    page = max(0, min(page, total_pages - 1))
    context.user_data["date_page"] = page
    start = page * per_page
    end = start + per_page
    chunk = dates[start:end]
    kb = [[InlineKeyboardButton(d.strftime("%d.%m.%Y"), callback_data=f"d:{d}")] for d in chunk]
    if total_pages > 1:
        kb.append([
            InlineKeyboardButton("◀️", callback_data="prev"),
            InlineKeyboardButton(f"{page + 1} / {total_pages}", callback_data="noop"),
            InlineKeyboardButton("▶️", callback_data="next"),
        ])
    kb.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
    markup = InlineKeyboardMarkup(kb)
    if getattr(getattr(msg, "from_user", None), "is_bot", False):
        await msg.edit_text("Оберіть дату:", reply_markup=markup)
    else:
        await msg.reply_text("Оберіть дату:", reply_markup=markup)
    return FILTER_DATES_LIST


async def dates_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "prev":
        page = context.user_data.get("date_page", 0)
        if page > 0:
            context.user_data["date_page"] = page - 1
        return await _show_dates_page(query.message, context)
    if data == "next":
        dates = context.user_data.get("dates", [])
        per_page = 10
        total_pages = max(1, ceil(len(dates) / per_page))
        page = context.user_data.get("date_page", 0)
        if page < total_pages - 1:
            context.user_data["date_page"] = page + 1
        return await _show_dates_page(query.message, context)
    if data == "back":
        await start(query.message, context)
        return FILTER_DATE_MODE
    if data.startswith("d:"):
        d = datetime.strptime(data.split(":", 1)[1], "%Y-%m-%d").date()
        rows = await database.fetch_all(
            sqlalchemy.select(CRMEvent)
            .where(sqlalchemy.func.date(CRMEvent.c.event_datetime) == d)
            .order_by(CRMEvent.c.event_datetime)
        )
        await _show_selected_day(query.message, rows)
        return ConversationHandler.END
    return FILTER_DATES_LIST


async def _show_selected_day(msg, rows):
    if not rows:
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔁 Спробувати знову", callback_data="retry_event_filter")],
                [InlineKeyboardButton("❌ Вийти", callback_data="cancel_event_filter")],
            ]
        )
        await msg.edit_text(
            "📭 Подій не знайдено за вибраним критерієм.",
            reply_markup=reply_markup,
        )
        return
    texts = [await format_event(r) for r in rows]
    await msg.reply_text("\n\n".join(texts))


async def _show_all_start(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent)
        .where(CRMEvent.c.status == "planned")
        .order_by(CRMEvent.c.event_datetime.asc())
    )
    context.user_data["ev_rows"] = [dict(r) for r in rows]
    context.user_data["ev_page"] = 0
    push_state(context, FILTER_ALL_EVENTS)
    return await _show_page(msg, context)


async def page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔁 Спробувати знову", callback_data="retry_event_filter")],
                [InlineKeyboardButton("❌ Вийти", callback_data="cancel_event_filter")],
            ]
        )
        await msg.reply_text(
            "📭 Подій не знайдено за вибраним критерієм.",
            reply_markup=reply_markup,
        )
        return ConversationHandler.END

    total_pages = max(1, ceil(len(rows) / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    context.user_data["ev_page"] = page
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = rows[start:end]
    texts = [await format_event(r) for r in chunk]
    text = "\n\n".join(texts)

    kb: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        kb.append([
            InlineKeyboardButton("◀️ Назад", callback_data="prev"),
            InlineKeyboardButton(f"{page + 1} / {total_pages}", callback_data="noop"),
            InlineKeyboardButton("▶️ Далі", callback_data="next"),
        ])
    markup = InlineKeyboardMarkup(kb)

    if getattr(getattr(msg, "from_user", None), "is_bot", False):
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.reply_text(text, reply_markup=markup)
    return FILTER_ALL_EVENTS


