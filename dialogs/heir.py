import os
from datetime import datetime
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
from db import database, Payer, add_heir as db_add_heir, transfer_assets_to_heir
from ftp_utils import upload_file_ftp

# FSM states
CONFIRM, HEIR_ID, COLLECT_DOCS, PAYMENT = range(4)

BACK_BTN = "⬅️ Назад"
CANCEL_BTN = "❌ Скасувати"
back_cancel_keyboard = ReplyKeyboardMarkup(
    [[BACK_BTN, CANCEL_BTN]], resize_keyboard=True
)

ALLOWED_EXT = {"pdf", "jpg", "jpeg", "png"}

async def start_add_heir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for adding heir."""
    query = update.callback_query
    deceased_id = int(query.data.split(":")[1])
    payer = await database.fetch_one(Payer.select().where(Payer.c.id == deceased_id))
    if not payer:
        await query.answer("Пайовик не знайдений", show_alert=True)
        return ConversationHandler.END
    if not payer["is_deceased"]:
        await query.answer("Пайовик не має статусу 'Помер'", show_alert=True)
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["deceased_id"] = deceased_id
    context.user_data["docs"] = []
    await query.message.edit_text(
        f"Додаємо спадкоємця для <b>{payer['name']}</b> 🕯\nПідтвердіть дію.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Продовжити", callback_data="heir_confirm")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="heir_cancel")],
        ]),
        parse_mode="HTML",
    )
    return CONFIRM

async def confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "heir_cancel":
        await query.message.edit_text("Скасовано")
        context.user_data.clear()
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton("🔍 Існуючий пайовик", callback_data="heir_existing")],
        [InlineKeyboardButton("➕ Новий спадкоємець", callback_data="heir_new")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="heir_cancel")],
    ]
    await query.message.edit_text(
        "Оберіть дію:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return HEIR_ID

async def choose_heir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "heir_cancel":
        await query.message.edit_text("Скасовано")
        context.user_data.clear()
        return ConversationHandler.END
    if query.data == "heir_new":
        await query.message.edit_text(
            "Спочатку додайте нового пайовика через меню «➕ Додати пайовика».\n"
            "Після створення повторно запустіть додавання спадкоємця та оберіть \"Існуючий пайовик\".")
        return ConversationHandler.END
    await query.message.edit_text(
        "Надішліть ID існуючого спадкоємця:",
        reply_markup=back_cancel_keyboard,
    )
    return HEIR_ID

async def receive_heir_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == CANCEL_BTN:
        await update.message.reply_text("Скасовано", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    if text == BACK_BTN:
        await update.message.reply_text(
            "Оберіть дію:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Існуючий пайовик", callback_data="heir_existing")],
                [InlineKeyboardButton("➕ Новий спадкоємець", callback_data="heir_new")],
                [InlineKeyboardButton("❌ Скасувати", callback_data="heir_cancel")],
            ]),
        )
        return HEIR_ID
    if not text.isdigit():
        await update.message.reply_text("Введіть числовий ID", reply_markup=back_cancel_keyboard)
        return HEIR_ID
    heir_id = int(text)
    deceased_id = context.user_data.get("deceased_id")
    if heir_id == deceased_id:
        await update.message.reply_text("ID співпадають. Введіть інший ID", reply_markup=back_cancel_keyboard)
        return HEIR_ID
    heir = await database.fetch_one(Payer.select().where(Payer.c.id == heir_id))
    if not heir:
        await update.message.reply_text("Пайовика не знайдено. Спробуйте ще раз.", reply_markup=back_cancel_keyboard)
        return HEIR_ID
    context.user_data["heir_id"] = heir_id
    await update.message.reply_text(
        "Надішліть до 3 файлів (PDF/JPEG/PNG) для підтвердження. Коли завершите — натисніть \"Готово\".",
        reply_markup=ReplyKeyboardMarkup(
            [["Готово", CANCEL_BTN]], resize_keyboard=True
        ),
    )
    return COLLECT_DOCS

async def collect_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Готово":
        return await finish_docs(update, context)
    if update.message.text == CANCEL_BTN:
        await update.message.reply_text("Скасовано", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    docs = context.user_data.setdefault("docs", [])
    if len(docs) >= 3:
        await update.message.reply_text("Ви вже завантажили 3 файли. Натисніть 'Готово'.")
        return COLLECT_DOCS
    file = None
    filename = None
    if update.message.document:
        file = await update.message.document.get_file()
        filename = update.message.document.file_name
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        filename = f"photo_{datetime.utcnow().timestamp()}.jpg"
    else:
        await update.message.reply_text("Невідомий формат. Надішліть файл або фото.")
        return COLLECT_DOCS
    ext = filename.split(".")[-1].lower()
    if ext not in ALLOWED_EXT:
        await update.message.reply_text("Дозволені формати: PDF, JPEG, PNG")
        return COLLECT_DOCS
    os.makedirs("temp_docs", exist_ok=True)
    local_path = os.path.join("temp_docs", filename)
    await file.download_to_drive(local_path)
    remote_path = f"heirs/{context.user_data['deceased_id']}/{filename}"
    try:
        upload_file_ftp(local_path, remote_path)
        docs.append(remote_path)
        await update.message.reply_text("Файл збережено. Надішліть ще або натисніть 'Готово'.")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
    return COLLECT_DOCS

async def finish_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    docs = context.user_data.get("docs", [])
    deceased_id = context.user_data.get("deceased_id")
    heir_id = context.user_data.get("heir_id")
    await db_add_heir(deceased_id, heir_id, documents=docs)
    land_cnt, contract_cnt = await transfer_assets_to_heir(deceased_id, heir_id)
    await update.message.reply_text(
        "Спадкоємця додано.", reply_markup=ReplyKeyboardRemove()
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Так", callback_data="pay_yes"), InlineKeyboardButton("Ні", callback_data="pay_no")]
    ])
    await update.message.reply_text(
        f"Передано {land_cnt} ділянок та {contract_cnt} договорів.\n"
        "Пропозиція виплатити спадкоємцю зараз?",
        reply_markup=keyboard,
    )
    return PAYMENT

async def payment_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "pay_yes":
        await query.message.edit_text("Виплата поки не реалізована.")
    else:
        await query.message.edit_text("Готово.")
    context.user_data.clear()
    return ConversationHandler.END

add_heir_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_heir, pattern=r"^add_heir:\d+$")],
    states={
        CONFIRM: [CallbackQueryHandler(confirm_step, pattern=r"^heir_(confirm|cancel)$")],
        HEIR_ID: [CallbackQueryHandler(choose_heir, pattern=r"^heir_(existing|new|cancel)$"),
                  MessageHandler(filters.TEXT & ~filters.COMMAND, receive_heir_id)],
        COLLECT_DOCS: [MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT, collect_docs)],
        PAYMENT: [CallbackQueryHandler(payment_step, pattern=r"^pay_(yes|no)$")],
    },
    fallbacks=[],
    allow_reentry=True,
)
