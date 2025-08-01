from __future__ import annotations

from datetime import datetime
from math import ceil

import sqlalchemy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import database, CRMEvent
from crm.event_fsm_navigation import (
    CANCEL_BTN,
    push_state,
    handle_back_cancel,
    cancel_handler,
    show_crm_menu,
)
from crm.event_utils import format_event

# conversation states
MODE_CHOOSE, SHOW_PAGE, SHOW_CARD = range(3)
PAGE_SIZE = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show view mode choice."""
    context.user_data.clear()
    context.user_data["fsm_history"] = []
    push_state(context, MODE_CHOOSE)
    kb = ReplyKeyboardMarkup(
        [["1️⃣ Події на сьогодні"], ["2️⃣ Найближчі події"], ["⬅️ Назад", CANCEL_BTN]],
        resize_keyboard=True,
    )
    await update.message.reply_text("📅 Оберіть режим перегляду:", reply_markup=kb)
    return MODE_CHOOSE


async def mode_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mode selection."""
    result = await handle_back_cancel(update, context, show_crm_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    if text.startswith("1"):
        return await _show_today(update.message)
    if text.startswith("2"):
        rows = await database.fetch_all(
            sqlalchemy.select(CRMEvent)
            .where(CRMEvent.c.status == "planned")
            .order_by(CRMEvent.c.event_datetime.asc())
        )
        context.user_data["ev_rows"] = [dict(r) for r in rows]
        context.user_data["ev_page"] = 0
        push_state(context, SHOW_PAGE)
        return await _show_page(update.message, context)
    await update.message.reply_text("Оберіть режим з меню:")
    return MODE_CHOOSE


async def _show_today(msg) -> int:
    today = datetime.now().date()
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent)
        .where(sqlalchemy.func.date(CRMEvent.c.event_datetime) == today)
        .order_by(CRMEvent.c.event_datetime.asc())
    )
    if not rows:
        await msg.reply_text("📭 Подій не знайдено.")
        return ConversationHandler.END
    texts = [await format_event(r) for r in rows]
    await msg.reply_text("\n\n".join(texts))
    return ConversationHandler.END


async def page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle pagination buttons."""
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


async def view_event_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Open single event card."""
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(CRMEvent).where(CRMEvent.c.id == event_id))
    if not row:
        await query.answer("Не знайдено", show_alert=True)
        return SHOW_PAGE
    context.user_data["current_event_id"] = event_id
    push_state(context, SHOW_CARD)
    text = await _event_card_text(row)
    await query.message.edit_text(text, reply_markup=_event_card_kb(event_id))
    return SHOW_CARD


def _event_card_kb(eid: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("✅ Виконано", callback_data=f"done:{eid}")],
        [InlineKeyboardButton("❌ Скасувати", callback_data=f"cancel:{eid}")],
        [InlineKeyboardButton("📝 Змінити", callback_data=f"edit:{eid}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_page")],
    ]
    return InlineKeyboardMarkup(kb)


async def _event_card_text(row) -> str:
    text = await format_event(row)
    status_map = {"planned": "⏳ Заплановано", "done": "✅ Виконано", "canceled": "❌ Скасовано"}
    text += f"\nСтатус: {status_map.get(row['status'], row['status'])}"
    return text


async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split(":")[1])
    await database.execute(
        CRMEvent.update().where(CRMEvent.c.id == event_id).values(status="done")
    )
    row = await database.fetch_one(sqlalchemy.select(CRMEvent).where(CRMEvent.c.id == event_id))
    await query.message.edit_text(await _event_card_text(row), reply_markup=_event_card_kb(event_id))
    return SHOW_CARD


async def mark_canceled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split(":")[1])
    await database.execute(
        CRMEvent.update().where(CRMEvent.c.id == event_id).values(status="canceled")
    )
    row = await database.fetch_one(sqlalchemy.select(CRMEvent).where(CRMEvent.c.id == event_id))
    await query.message.edit_text(await _event_card_text(row), reply_markup=_event_card_kb(event_id))
    return SHOW_CARD


async def edit_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Функція в розробці", show_alert=True)
    return SHOW_CARD


async def back_to_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pop_state = context.user_data.get("fsm_history", [])
    if pop_state:
        pop_state.pop()
    return await _show_page(query.message, context)


async def page_text_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle back/cancel text while viewing pages."""
    result = await handle_back_cancel(update, context, show_crm_menu)
    if result is None:
        return SHOW_PAGE
    if result == MODE_CHOOSE:
        await start(update, context)
        return MODE_CHOOSE
    return result


async def card_text_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text while viewing event card."""
    result = await handle_back_cancel(update, context, show_crm_menu)
    if result is None:
        return SHOW_CARD
    if result == SHOW_PAGE:
        return await _show_page(update.message, context)
    return result


async def _show_page(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = context.user_data.get("ev_rows", [])
    page = context.user_data.get("ev_page", 0)
    if not rows:
        await msg.reply_text("📭 Подій не знайдено.")
        return ConversationHandler.END

    total_pages = max(1, ceil(len(rows) / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    context.user_data["ev_page"] = page
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = rows[start:end]
    texts = [await format_event(r) for r in chunk]
    text = "\n\n".join(texts)

    kb: list[list[InlineKeyboardButton]] = [[InlineKeyboardButton("➡️ Переглянути", callback_data=f"view:{r['id']}")] for r in chunk]

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
    return SHOW_PAGE


view_events_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📅 Події за датою$"), start)],
    states={
        MODE_CHOOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mode_input)],
        SHOW_PAGE: [
            CallbackQueryHandler(page_cb, pattern="^(prev|next)$"),
            CallbackQueryHandler(view_event_cb, pattern=r"^view:\d+$"),
            CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, page_text_cb),
        ],
        SHOW_CARD: [
            CallbackQueryHandler(mark_done, pattern=r"^done:\d+$"),
            CallbackQueryHandler(mark_canceled, pattern=r"^cancel:\d+$"),
            CallbackQueryHandler(edit_event, pattern=r"^edit:\d+$"),
            CallbackQueryHandler(back_to_page, pattern="^back_to_page$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, card_text_cb),
        ],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_crm_menu))],
)
