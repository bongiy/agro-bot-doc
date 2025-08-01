"""FSM for adding payer requests/inquiries."""

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
from ftp_utils import upload_file_ftp
from utils.fsm_navigation import (
    BACK_BTN,
    CANCEL_BTN,
    back_cancel_keyboard,
    push_state,
    handle_back_cancel,
    cancel_handler,
)

(
    CHOOSE_PAYER,
    SEARCH_INPUT,
    CHOOSE_TYPE,
    CUSTOM_TYPE,
    DESCRIPTION,
    DATE_CHOICE,
    DATE_INPUT,
    STATUS_CHOOSE,
    DOCUMENT,
    CONFIRM,
) = range(10)

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


async def inbox_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from keyboards.menu import crm_inbox_menu
    await update.message.reply_text(
        "Меню «Звернення та заяви»",
        reply_markup=crm_inbox_menu,
    )
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["fsm_history"] = []
    push_state(context, CHOOSE_PAYER)

    recent = await database.fetch_all(
        sqlalchemy.select(Payer).order_by(Payer.c.id.desc()).limit(3)
    )
    keyboard = [
        [InlineKeyboardButton(f"{p['id']}: {p['name']}", callback_data=f"payer:{p['id']}")]
        for p in recent
    ]
    keyboard.append([InlineKeyboardButton("🔍 Пошук пайовика", callback_data="search")])
    await update.message.reply_text(
        "Оберіть пайовика:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_PAYER


async def choose_payer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "search":
        push_state(context, SEARCH_INPUT)
        await query.message.edit_text("Введіть частину ПІБ:", reply_markup=back_cancel_keyboard)
        return SEARCH_INPUT
    pid = int(data.split(":")[1])
    context.user_data["payer_id"] = pid
    return await show_type_step(query.message, context)


async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, inbox_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    rows = await database.fetch_all(
        sqlalchemy.select(Payer).where(Payer.c.name.ilike(f"%{text}%")).limit(10)
    )
    if not rows:
        await update.message.reply_text("Не знайдено. Спробуйте ще:")
        return SEARCH_INPUT
    keyboard = [
        [InlineKeyboardButton(f"{r['name']} (ID:{r['id']})", callback_data=f"payer:{r['id']}")]
        for r in rows
    ]
    keyboard.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
    await update.message.reply_text(
        "Оберіть пайовика:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_PAYER


async def search_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await start(query, context)


async def show_type_step(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    push_state(context, CHOOSE_TYPE)
    keyboard = [
        [InlineKeyboardButton(txt, callback_data=f"rtype:{key}")]
        for key, txt in REQUEST_TYPES.items()
    ]
    await msg.edit_text(
        "Оберіть тип звернення:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_TYPE


async def type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    typ = query.data.split(":")[1]
    if typ == "other":
        push_state(context, CUSTOM_TYPE)
        await query.message.edit_text("Введіть тип звернення:", reply_markup=back_cancel_keyboard)
        return CUSTOM_TYPE
    context.user_data["req_type"] = REQUEST_TYPES[typ]
    return await ask_description(query.message, context)


async def custom_type_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, inbox_menu)
    if result is not None:
        return result
    context.user_data["req_type"] = update.message.text.strip()
    return await ask_description(update.message, context)


async def ask_description(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    push_state(context, DESCRIPTION)
    await msg.reply_text(
        "Введіть короткий опис (до 500 символів):",
        reply_markup=back_cancel_keyboard,
    )
    return DESCRIPTION


async def description_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, inbox_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    if len(text) > 500:
        await update.message.reply_text("До 500 символів. Спробуйте ще:")
        return DESCRIPTION
    context.user_data["description"] = text
    push_state(context, DATE_CHOICE)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("\U0001F4C5 Сьогодні", callback_data="today")],
            [InlineKeyboardButton("\u2328\ufe0f Ввести вручну", callback_data="manual")],
        ]
    )
    await update.message.reply_text("Оберіть дату звернення:", reply_markup=kb)
    return DATE_CHOICE


async def date_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == "today":
        context.user_data["date_submitted"] = datetime.utcnow().date()
        push_state(context, STATUS_CHOOSE)
        keyboard = [
            [InlineKeyboardButton(txt, callback_data=f"status:{key}")]
            for key, txt in STATUS_TYPES.items()
        ]
        await query.message.edit_text(
            "Оберіть статус:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STATUS_CHOOSE
    if choice == "manual":
        push_state(context, DATE_INPUT)
        await query.message.edit_text(
            "Введіть дату звернення (ДД.ММ.РРРР):",
            reply_markup=back_cancel_keyboard,
        )
        return DATE_INPUT
    return DATE_CHOICE


async def date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, inbox_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    try:
        date_val = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Формат дати ДД.ММ.РРРР:")
        return DATE_INPUT
    context.user_data["date_submitted"] = date_val
    push_state(context, STATUS_CHOOSE)
    keyboard = [
        [InlineKeyboardButton(txt, callback_data=f"status:{key}")]
        for key, txt in STATUS_TYPES.items()
    ]
    await update.message.reply_text(
        "Оберіть статус:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATUS_CHOOSE


async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    status = query.data.split(":")[1]
    context.user_data["status"] = STATUS_TYPES[status]
    push_state(context, DOCUMENT)
    await query.message.edit_text(
        "Надішліть документ (фото або PDF):",
        reply_markup=back_cancel_keyboard,
    )
    return DOCUMENT


async def document_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, inbox_menu)
    if result is not None:
        return result
    doc = update.message.document
    photo = update.message.photo[-1] if update.message.photo else None
    if not doc and not photo:
        await update.message.reply_text("Надішліть файл або фото:")
        return DOCUMENT
    if doc:
        file = await doc.get_file()
        ext = os.path.splitext(doc.file_name or "")[1] or ".pdf"
    else:
        file = await photo.get_file()
        ext = ".jpg"
    local_path = f"temp_{update.effective_user.id}_{int(datetime.utcnow().timestamp())}{ext}"
    await file.download_to_drive(local_path)
    context.user_data["document_local"] = local_path
    context.user_data["document_ext"] = ext
    return await show_confirm(update.message, context)


async def show_confirm(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    push_state(context, CONFIRM)
    pid = context.user_data.get("payer_id")
    payer = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == pid))
    text = (
        f"<b>{payer['name']}</b> (ID: {pid})\n"
        f"Тип: {context.user_data.get('req_type')}\n"
        f"Опис: {context.user_data.get('description')}\n"
        f"Дата: {context.user_data.get('date_submitted').strftime('%d.%m.%Y')}\n"
        f"Статус: {context.user_data.get('status')}\n"
        "\nЗберегти звернення?"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💾 Зберегти", callback_data="save")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
        ]
    )
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")
    return CONFIRM


async def confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        push_state(context, DOCUMENT)
        await query.message.edit_text(
            "Надішліть документ (фото або PDF):",
            reply_markup=back_cancel_keyboard,
        )
        return DOCUMENT
    if data == "cancel":
        await query.message.edit_text("Скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    # save
    pid = context.user_data.get("payer_id")
    req_type = context.user_data.get("req_type")
    desc = context.user_data.get("description")
    date_val = context.user_data.get("date_submitted")
    status = context.user_data.get("status")

    req_id = await database.execute(
        PayerRequest.insert().values(
            payer_id=pid,
            type=req_type,
            description=desc,
            date_submitted=date_val,
            status=status,
            created_at=datetime.utcnow(),
        )
    )

    remote_path = None
    local_path = context.user_data.get("document_local")
    if local_path:
        remote_path = f"requests/payer_{pid}_request_{req_id}{context.user_data.get('document_ext')}"
        upload_file_ftp(local_path, remote_path)
        os.remove(local_path)
        await database.execute(
            PayerRequest.update()
            .where(PayerRequest.c.id == req_id)
            .values(document_path=remote_path)
        )

    await query.message.edit_text("✅ Звернення збережено")
    context.user_data.clear()
    return ConversationHandler.END


add_request_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати звернення$"), start)],
    states={
        CHOOSE_PAYER: [CallbackQueryHandler(choose_payer_cb, pattern=r"^(payer:\d+|search)$")],
        SEARCH_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_input),
            CallbackQueryHandler(search_back_cb, pattern="^back$")
        ],
        CHOOSE_TYPE: [CallbackQueryHandler(type_cb, pattern=r"^rtype:\w+$")],
        CUSTOM_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_type_input)],
        DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_input)],
        DATE_CHOICE: [CallbackQueryHandler(date_choice_cb, pattern=r"^(today|manual)$")],
        DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_input)],
        STATUS_CHOOSE: [CallbackQueryHandler(status_cb, pattern=r"^status:\w+$")],
        DOCUMENT: [MessageHandler(filters.Document.ALL | filters.PHOTO, document_input)],
        CONFIRM: [CallbackQueryHandler(confirm_cb, pattern=r"^(save|back|cancel)$")],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(inbox_menu))],
)

