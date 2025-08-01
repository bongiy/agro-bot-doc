from __future__ import annotations

from datetime import datetime
import os
import sqlalchemy

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from db import database, PayerRequest, Payer, User
from ftp_utils import upload_file_ftp, delete_file_ftp

BACK_BTN = "⬅️ Назад"
CANCEL_BTN = "❌ Скасувати"
back_cancel_keyboard = ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True)

STATUS_TYPES = {
    "new": "Нове",
    "in_progress": "В роботі",
    "closed": "Закрите",
}

(
    SHOW_CARD,
    STATUS_CHOOSE,
    DOC_MENU,
    DOC_UPLOAD,
    RESPONSIBLE_CHOOSE,
) = range(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    rid = int(query.data.split(":")[1])
    context.user_data.clear()
    context.user_data["req_id"] = rid
    return await _show_card(query.message, context)


async def _get_request(rid: int):
    row = await database.fetch_one(
        sqlalchemy.select(PayerRequest).where(PayerRequest.c.id == rid)
    )
    return dict(row) if row else None


async def _show_card(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    rid = context.user_data.get("req_id")
    row = await _get_request(rid)
    if not row:
        await msg.edit_text("Звернення не знайдено.")
        return ConversationHandler.END
    payer = await database.fetch_one(
        sqlalchemy.select(Payer).where(Payer.c.id == row["payer_id"])
    )
    user_txt = "-"
    if row.get("responsible_user_id"):
        user = await database.fetch_one(
            sqlalchemy.select(User).where(User.c.id == row["responsible_user_id"])
        )
        if user:
            user_txt = user["full_name"] or str(user["id"])
    d = row["date_submitted"].strftime("%d.%m.%Y") if row["date_submitted"] else "-"
    text = (
        f"🏷️ {row['type']}\n"
        f"📆 {d}\n"
        f"🧑 {payer['name'] if payer else row['payer_id']}\n"
        f"📝 {row['description'] or '-'}\n"
        f"🚦 {row['status']}\n"
        f"👤 {user_txt}"
    )
    kb = [
        [InlineKeyboardButton("✏️ Змінити статус", callback_data="status")],
        [InlineKeyboardButton("📎 Документ", callback_data="document")],
        [InlineKeyboardButton("👤 Відповідальний", callback_data="responsible")],
        [InlineKeyboardButton(CANCEL_BTN, callback_data="cancel")],
    ]
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return SHOW_CARD


async def card_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "status":
        kb = [
            [InlineKeyboardButton(txt, callback_data=f"set_status:{k}")]
            for k, txt in STATUS_TYPES.items()
        ]
        kb.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
        kb.append([InlineKeyboardButton(CANCEL_BTN, callback_data="cancel")])
        await query.message.edit_text(
            "Оберіть статус:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return STATUS_CHOOSE
    if data == "document":
        rid = context.user_data.get("req_id")
        row = await _get_request(rid)
        if not row:
            await query.answer("Помилка", show_alert=True)
            return ConversationHandler.END
        if row["document_path"]:
            kb = [
                [InlineKeyboardButton("🔁 Замінити документ", callback_data="upload")],
                [InlineKeyboardButton("❌ Видалити документ", callback_data="delete")],
            ]
        else:
            kb = [[InlineKeyboardButton("📤 Завантажити документ", callback_data="upload")]]
        kb.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
        kb.append([InlineKeyboardButton(CANCEL_BTN, callback_data="cancel")])
        await query.message.edit_text(
            "Документ:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return DOC_MENU
    if data == "responsible":
        rows = await database.fetch_all(
            sqlalchemy.select(User).where(User.c.is_active == True).order_by(User.c.id)
        )
        kb = [
            [InlineKeyboardButton(r["full_name"] or str(r["id"]), callback_data=f"user:{r['id']}")]
            for r in rows[:10]
        ]
        kb.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
        kb.append([InlineKeyboardButton(CANCEL_BTN, callback_data="cancel")])
        await query.message.edit_text(
            "Оберіть відповідального:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return RESPONSIBLE_CHOOSE
    if data == "back":
        return await _show_card(query.message, context)
    if data == "cancel":
        await query.message.edit_text("❌ Редагування скасовано.")
        context.user_data.clear()
        return ConversationHandler.END
    return SHOW_CARD


async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        return await _show_card(query.message, context)
    if data == "cancel":
        await query.message.edit_text("❌ Редагування скасовано.")
        context.user_data.clear()
        return ConversationHandler.END
    if data.startswith("set_status:"):
        st = data.split(":")[1]
        rid = context.user_data.get("req_id")
        await database.execute(
            PayerRequest.update()
            .where(PayerRequest.c.id == rid)
            .values(status=STATUS_TYPES[st])
        )
        return await _show_card(query.message, context)
    return STATUS_CHOOSE


async def document_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    rid = context.user_data.get("req_id")
    if data == "back":
        return await _show_card(query.message, context)
    if data == "cancel":
        await query.message.edit_text("❌ Редагування скасовано.")
        context.user_data.clear()
        return ConversationHandler.END
    if data == "delete":
        row = await _get_request(rid)
        if row and row["document_path"]:
            try:
                delete_file_ftp(row["document_path"])
            except Exception:
                pass
            await database.execute(
                PayerRequest.update()
                .where(PayerRequest.c.id == rid)
                .values(document_path=None)
            )
        return await _show_card(query.message, context)
    if data == "upload":
        context.user_data["await_doc"] = True
        await query.message.edit_text(
            "Надішліть файл (.pdf, .jpg, .jpeg, .png):",
            reply_markup=back_cancel_keyboard,
        )
        return DOC_UPLOAD
    return DOC_MENU


async def document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text if update.message else None
    if text == CANCEL_BTN:
        await update.message.reply_text(
            "❌ Редагування скасовано.", reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END
    if text == BACK_BTN:
        await update.message.reply_text("", reply_markup=ReplyKeyboardRemove())
        return await _show_card(update.message, context)
    doc = update.message.document
    photo = update.message.photo[-1] if update.message.photo else None
    if not doc and not photo:
        await update.message.reply_text("Надішліть файл або фото:")
        return DOC_UPLOAD
    if doc:
        file = await doc.get_file()
        ext = os.path.splitext(doc.file_name or "")[1] or ".pdf"
    else:
        file = await photo.get_file()
        ext = ".jpg"
    rid = context.user_data.get("req_id")
    row = await _get_request(rid)
    local_path = f"temp_req_{rid}{ext}"
    await file.download_to_drive(local_path)
    remote_path = f"requests/payer_{row['payer_id']}_request_{rid}{ext}"
    upload_file_ftp(local_path, remote_path)
    os.remove(local_path)
    await database.execute(
        PayerRequest.update()
        .where(PayerRequest.c.id == rid)
        .values(document_path=remote_path)
    )
    await update.message.reply_text("Документ збережено.", reply_markup=ReplyKeyboardRemove())
    return await _show_card(update.message, context)


async def responsible_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        return await _show_card(query.message, context)
    if data == "cancel":
        await query.message.edit_text("❌ Редагування скасовано.")
        context.user_data.clear()
        return ConversationHandler.END
    if data.startswith("user:"):
        rid = context.user_data.get("req_id")
        uid = int(data.split(":")[1])
        await database.execute(
            PayerRequest.update()
            .where(PayerRequest.c.id == rid)
            .values(responsible_user_id=uid)
        )
        return await _show_card(query.message, context)
    return RESPONSIBLE_CHOOSE


update_request_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start, pattern=r"^update_request:\d+$")],
    states={
        SHOW_CARD: [
            CallbackQueryHandler(card_cb, pattern=r"^(status|document|responsible|cancel|back)$")
        ],
        STATUS_CHOOSE: [CallbackQueryHandler(status_cb, pattern=r"^(set_status:\w+|back|cancel)$")],
        DOC_MENU: [CallbackQueryHandler(document_menu_cb, pattern=r"^(upload|delete|back|cancel)$")],
        DOC_UPLOAD: [MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT, document_upload)],
        RESPONSIBLE_CHOOSE: [CallbackQueryHandler(responsible_cb, pattern=r"^(user:\d+|back|cancel)$")],
    },
    fallbacks=[],
)
