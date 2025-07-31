from __future__ import annotations

from datetime import datetime
import sqlalchemy

from telegram import Update, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from db import database, CRMEvent
from utils.fsm_navigation import (
    back_cancel_keyboard,
    push_state,
    cancel_handler,
    CANCEL_BTN,
)
from crm.events import (
    DATE_INPUT,
    TYPE_CHOOSE,
    COMMENT_INPUT,
    RESPONSIBLE_CHOOSE,
    RESPONSIBLE_ID,
    set_date,
    type_cb,
    save_comment,
    responsible_cb,
    responsible_id_input,
    show_menu,
)

STATUS_ICONS = {
    "planned": "\u23F3",  # ⏳
    "done": "\u2705",     # ✅
    "canceled": "\u274C",  # ❌
}


async def get_events_text(entity_type: str, entity_id: int) -> str:
    query = (
        sqlalchemy.select(CRMEvent)
        .where(
            CRMEvent.c.entity_type == entity_type,
            CRMEvent.c.entity_id == entity_id,
        )
        .order_by(CRMEvent.c.event_datetime.desc())
        .limit(5)
    )
    rows = await database.fetch_all(query)
    if not rows:
        return "\U0001F4C5 \u041F\u043E\u0434\u0456\u0439 \u043D\u0435 \u0437\u0430\u043F\u043B\u0430\u043D\u043E\u0432\u0430\u043D\u043E."
    lines = [
        f"\u2022 {r['event_datetime'].strftime('%d.%m.%Y %H:%M')} \u2014 {r['event_type']} \u2014 {STATUS_ICONS.get(r['status'], '')}"
        for r in rows
    ]
    return "\U0001F4C5 \u041F\u043E\u0434\u0456\u0457:\n" + "\n".join(lines)


def events_button(entity_type: str, entity_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        "\u2795 \u0414\u043E\u0434\u0430\u0442\u0438 \u043F\u043E\u0434\u0456\u044E",
        callback_data=f"add_event:{entity_type}:{entity_id}",
    )


async def add_event_from_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, entity_type, entity_id = query.data.split(":")

    context.user_data.clear()
    context.user_data["fsm_history"] = []
    context.user_data["entity_type"] = entity_type
    context.user_data["entity_id"] = int(entity_id)

    push_state(context, DATE_INPUT)
    await query.message.reply_text(
        "\u0412\u0432\u0435\u0434\u0456\u0442\u044C \u0434\u0430\u0442\u0443 \u0442\u0430 \u0447\u0430\u0441 \u043F\u043E\u0434\u0456\u0457 (\u0414\u0414.\u041C.\u0420\u0420\u0420\u0420 \u0413\u0413:\u0425\u0425). \u042F\u043A\u0449\u043E \u0447\u0430\u0441 \u043D\u0435 \u0432\u043A\u0430\u0437\u0430\u043D\u043E, \u0431\u0443\u0434\u0435 09:00",
        reply_markup=back_cancel_keyboard,
    )
    return DATE_INPUT


add_event_from_card_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            add_event_from_card,
            pattern=r"^add_event:(payer|contract|land|potential_payer):\d+$",
        )
    ],
    states={
        DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_date)],
        TYPE_CHOOSE: [CallbackQueryHandler(type_cb, pattern=r"^(etype:\d+|back)$")],
        COMMENT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_comment)],
        RESPONSIBLE_CHOOSE: [CallbackQueryHandler(responsible_cb, pattern=r"^(resp:(self|other)|user:\d+|manual|back)$")],
        RESPONSIBLE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, responsible_id_input)],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_menu))],
)
