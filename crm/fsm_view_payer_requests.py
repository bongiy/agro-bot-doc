"""FSM for viewing payer requests with filtering and pagination."""

from __future__ import annotations

from math import ceil
from datetime import datetime
import os
import sqlalchemy

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import database, Payer, PayerRequest
from ftp_utils import download_file_ftp
from crm.event_fsm_navigation import (
    BACK_BTN,
    CANCEL_BTN,
    back_cancel_keyboard,
    push_state,
    handle_back_cancel,
    cancel_handler,
    show_crm_menu,
)

REQUEST_TYPES = {
    "pay": "Заява на виплату",
    "death": "Повідомлення про смерть",
    "reissue": "Заява на переоформлення",
    "other": "Інше",
}

STATUS_TYPES = {
    "new": "Нове",
    "in_progress": "В роботі",
    "closed": "Закрите",
}

(
    FILTER_MENU,
    FILTER_FIO,
    FILTER_TYPE,
    FILTER_STATUS,
    SHOW_LIST,
    SHOW_CARD,
    CHANGE_STATUS,
    DELETE_CONFIRM,
) = range(8)

PAGE_SIZE = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for request viewing."""
    context.user_data.clear()
    context.user_data["fsm_history"] = []
    push_state(context, FILTER_MENU)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔎 Пошук за ПІБ", callback_data="f:fio")],
            [InlineKeyboardButton("🏷️ Тип", callback_data="f:type")],
            [InlineKeyboardButton("🚦 Статус", callback_data="f:status")],
            [InlineKeyboardButton("📄 Показати всі", callback_data="f:all")],
        ]
    )
    await update.message.reply_text("Оберіть фільтр:", reply_markup=kb)
    return FILTER_MENU


async def filter_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ftype = query.data.split(":")[1]
    if ftype == "fio":
        push_state(context, FILTER_FIO)
        await query.message.edit_text(
            "Введіть частину ПІБ:", reply_markup=back_cancel_keyboard
        )
        return FILTER_FIO
    if ftype == "type":
        push_state(context, FILTER_TYPE)
        kb = [
            [InlineKeyboardButton(txt, callback_data=f"type:{k}")]
            for k, txt in REQUEST_TYPES.items()
        ]
        await query.message.edit_text(
            "Оберіть тип звернення:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return FILTER_TYPE
    if ftype == "status":
        push_state(context, FILTER_STATUS)
        kb = [
            [InlineKeyboardButton(txt, callback_data=f"status:{k}")]
            for k, txt in STATUS_TYPES.items()
        ]
        await query.message.edit_text(
            "Оберіть статус:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return FILTER_STATUS
    if ftype == "all":
        rows = await database.fetch_all(
            sqlalchemy.select(PayerRequest).order_by(PayerRequest.c.id.desc())
        )
        context.user_data["rows"] = [dict(r) for r in rows]
        context.user_data["page"] = 0
        return await _show_page(query.message, context)
    return FILTER_MENU


async def fio_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, show_crm_menu)
    if result is not None:
        if result == FILTER_MENU:
            return await start(update, context)
        return result
    text = update.message.text.strip()
    payers = await database.fetch_all(
        sqlalchemy.select(Payer).where(Payer.c.name.ilike(f"%{text}%"))
    )
    if not payers:
        await update.message.reply_text("Не знайдено. Спробуйте ще:")
        return FILTER_FIO
    ids = [p["id"] for p in payers]
    rows = await database.fetch_all(
        sqlalchemy.select(PayerRequest)
        .where(PayerRequest.c.payer_id.in_(ids))
        .order_by(PayerRequest.c.id.desc())
    )
    context.user_data["rows"] = [dict(r) for r in rows]
    context.user_data["page"] = 0
    return await _show_page(update.message, context)


async def type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    typ = query.data.split(":")[1]
    rows = await database.fetch_all(
        sqlalchemy.select(PayerRequest)
        .where(PayerRequest.c.type == REQUEST_TYPES[typ])
        .order_by(PayerRequest.c.id.desc())
    )
    context.user_data["rows"] = [dict(r) for r in rows]
    context.user_data["page"] = 0
    return await _show_page(query.message, context)


async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    st = query.data.split(":")[1]
    rows = await database.fetch_all(
        sqlalchemy.select(PayerRequest)
        .where(PayerRequest.c.status == STATUS_TYPES[st])
        .order_by(PayerRequest.c.id.desc())
    )
    context.user_data["rows"] = [dict(r) for r in rows]
    context.user_data["page"] = 0
    return await _show_page(query.message, context)


async def list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "prev":
        page = context.user_data.get("page", 0)
        if page > 0:
            context.user_data["page"] = page - 1
        return await _show_page(query.message, context)
    if data == "next":
        rows = context.user_data.get("rows", [])
        page = context.user_data.get("page", 0)
        total_pages = max(1, ceil(len(rows) / PAGE_SIZE))
        if page < total_pages - 1:
            context.user_data["page"] = page + 1
        return await _show_page(query.message, context)
    if data.startswith("open:"):
        rid = int(data.split(":")[1])
        return await _show_card(query.message, context, rid)
    if data == "back":
        return await start(update.callback_query, context)
    if data == "cancel":
        await query.message.edit_text("❌ Перегляд скасовано.")
        context.user_data.clear()
        return ConversationHandler.END
    return SHOW_LIST


async def _show_page(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = context.user_data.get("rows", [])
    page = context.user_data.get("page", 0)
    if not rows:
        await msg.edit_text("Звернень не знайдено.", reply_markup=None)
        return ConversationHandler.END
    total_pages = max(1, ceil(len(rows) / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    context.user_data["page"] = page
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = rows[start:end]
    texts = []
    keyboard = []
    for r in chunk:
        payer = await database.fetch_one(
            sqlalchemy.select(Payer).where(Payer.c.id == r["payer_id"])
        )
        pname = payer["name"] if payer else f"ID {r['payer_id']}"
        d = r["date_submitted"].strftime("%d.%m.%Y") if r["date_submitted"] else "-"
        texts.append(f"{r['id']}. {pname}\n{r['type']} | {d} | {r['status']}")
        keyboard.append([
            InlineKeyboardButton("➡️ Переглянути", callback_data=f"open:{r['id']}")
        ])
    if total_pages > 1:
        nav = [
            InlineKeyboardButton("⬅️", callback_data="prev"),
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton("➡️", callback_data="next"),
        ]
        keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="back"),
        InlineKeyboardButton("❌ Скасувати", callback_data="cancel"),
    ])
    markup = InlineKeyboardMarkup(keyboard)
    text = "\n\n".join(texts)
    if getattr(getattr(msg, "from_user", None), "is_bot", False):
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.reply_text(text, reply_markup=markup)
    return SHOW_LIST


async def _show_card(msg, context: ContextTypes.DEFAULT_TYPE, rid: int) -> int:
    row = await database.fetch_one(
        sqlalchemy.select(PayerRequest).where(PayerRequest.c.id == rid)
    )
    if not row:
        await msg.reply_text("Звернення не знайдено.")
        return ConversationHandler.END
    payer = await database.fetch_one(
        sqlalchemy.select(Payer).where(Payer.c.id == row["payer_id"])
    )
    pname = payer["name"] if payer else f"ID {row['payer_id']}"
    d = row["date_submitted"].strftime("%d.%m.%Y") if row["date_submitted"] else "-"
    text = (
        f"🏷️ {row['type']}\n"
        f"📆 {d}\n"
        f"🧑 {pname}\n"
        f"📝 {row['description'] or '-'}\n"
        f"🚦 {row['status']}"
    )
    kb = []
    if row["document_path"]:
        kb.append([InlineKeyboardButton("📎 Переглянути документ", callback_data=f"doc:{rid}")])
    kb.append([InlineKeyboardButton("✏️ Змінити статус", callback_data=f"chg_status:{rid}")])
    kb.append([InlineKeyboardButton("❌ Видалити", callback_data=f"del:{rid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back_list")])
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    context.user_data["current_rid"] = rid
    return SHOW_CARD


async def card_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    rid = context.user_data.get("current_rid")
    if data == "back_list":
        return await _show_page(query.message, context)
    if data.startswith("doc:"):
        rid = int(data.split(":")[1])
        row = await database.fetch_one(
            sqlalchemy.select(PayerRequest).where(PayerRequest.c.id == rid)
        )
        if row and row["document_path"]:
            tmp = f"temp_req_{rid}{os.path.splitext(row['document_path'])[1]}"
            try:
                download_file_ftp(row["document_path"], tmp)
                await query.message.reply_document(InputFile(tmp))
                os.remove(tmp)
            except Exception as e:
                await query.answer(f"Помилка: {e}", show_alert=True)
        else:
            await query.answer("Документ відсутній", show_alert=True)
        return SHOW_CARD
    if data.startswith("chg_status:"):
        rid = int(data.split(":")[1])
        kb = [
            [InlineKeyboardButton(txt, callback_data=f"set_status:{k}")]
            for k, txt in STATUS_TYPES.items()
        ]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back_card")])
        await query.message.edit_text(
            "Оберіть статус:", reply_markup=InlineKeyboardMarkup(kb)
        )
        context.user_data["current_rid"] = rid
        return CHANGE_STATUS
    if data.startswith("del:"):
        rid = int(data.split(":")[1])
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Так", callback_data=f"del_yes:{rid}")],
                [InlineKeyboardButton("❌ Ні", callback_data="back_card")],
            ]
        )
        await query.message.edit_text(
            "Видалити звернення?", reply_markup=kb
        )
        context.user_data["current_rid"] = rid
        return DELETE_CONFIRM
    return SHOW_CARD


async def status_set_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_card":
        rid = context.user_data.get("current_rid")
        return await _show_card(query.message, context, rid)
    if data.startswith("set_status:"):
        rid = context.user_data.get("current_rid")
        st = data.split(":")[1]
        await database.execute(
            PayerRequest.update()
            .where(PayerRequest.c.id == rid)
            .values(status=STATUS_TYPES[st])
        )
        return await _show_card(query.message, context, rid)
    return CHANGE_STATUS


async def delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_card":
        rid = context.user_data.get("current_rid")
        return await _show_card(query.message, context, rid)
    if data.startswith("del_yes:"):
        rid = int(data.split(":")[1])
        row = await database.fetch_one(
            sqlalchemy.select(PayerRequest).where(PayerRequest.c.id == rid)
        )
        if row and row["document_path"]:
            try:
                os.remove(row["document_path"])
            except Exception:
                pass
        await database.execute(
            PayerRequest.delete().where(PayerRequest.c.id == rid)
        )
        await query.message.edit_text("Звернення видалено", reply_markup=None)
        context.user_data.clear()
        return ConversationHandler.END
    return DELETE_CONFIRM


view_requests_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📂 Переглянути звернення$"), start)],
    states={
        FILTER_MENU: [CallbackQueryHandler(filter_menu_cb, pattern=r"^f:(fio|type|status|all)$")],
        FILTER_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fio_input)],
        FILTER_TYPE: [CallbackQueryHandler(type_cb, pattern=r"^type:\w+$")],
        FILTER_STATUS: [CallbackQueryHandler(status_cb, pattern=r"^status:\w+$")],
        SHOW_LIST: [CallbackQueryHandler(list_cb, pattern=r"^(prev|next|open:\d+|back|cancel)$")],
        SHOW_CARD: [CallbackQueryHandler(card_cb, pattern=r"^(doc:\d+|chg_status:\d+|del:\d+|back_list)$")],
        CHANGE_STATUS: [CallbackQueryHandler(status_set_cb, pattern=r"^(set_status:\w+|back_card)$")],
        DELETE_CONFIRM: [CallbackQueryHandler(delete_cb, pattern=r"^(del_yes:\d+|back_card)$")],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_crm_menu))],
)

