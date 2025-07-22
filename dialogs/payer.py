from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters
)
from db import database, Payer
from utils import *

# ---- СТАНИ ----
(
    FIO, IPN, OBLAST, RAYON, SELO, VUL, BUD, KV,
    PHONE, DOC_TYPE,
    PASS_SERIES, PASS_NUMBER, PASS_ISSUER, PASS_DATE,
    IDCARD_NUMBER, IDCARD_UNZR, IDCARD_ISSUER, IDCARD_DATE,
    BIRTH_DATE, EDIT_SELECT, EDIT_VALUE
) = range(21)

# ---- Клавіатури ----
menu_keyboard = ReplyKeyboardMarkup(
    [
        ["Новий пайовик", "Список пайовиків"],
        ["Додати ділянку", "Таблиця виплат"],
        ["Довідка"],
    ],
    resize_keyboard=True
)
doc_type_keyboard = ReplyKeyboardMarkup(
    [["Паспорт (книжка)", "ID картка"]], resize_keyboard=True
)
oblast_keyboard = ReplyKeyboardMarkup(
    [["Рівненська", "Інша"], ["❌ Скасувати"]], resize_keyboard=True
)
rayon_keyboard = ReplyKeyboardMarkup(
    [["Рівненський", "Дубенський", "Інший"], ["◀️ Назад", "❌ Скасувати"]], resize_keyboard=True
)
back_cancel_keyboard = ReplyKeyboardMarkup(
    [["◀️ Назад", "❌ Скасувати"]], resize_keyboard=True
)

# ---- Universal Back/Cancel handler ----
async def back_or_cancel(update, context, step_back):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Додавання скасовано.", reply_markup=menu_keyboard)
        context.user_data.clear()
        return ConversationHandler.END
    if text == "◀️ Назад":
        return step_back
    return None

# --- Далі весь код пайовика (add_payer_start ... add_payer_birth_date, show_payers, payer_card, edit... і т.д.)
# Можна просто перенести код із main.py — і працює!

# (Щоб не дублювати чат, якщо треба повністю — кину окремим файлом чи архівом, або сюди код одним блоком!)

# ---- ConversationHandler для пайовиків ----
add_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Новий пайовик$"), add_payer_start)],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_fio)],
        # ... (далі як було)
    },
    fallbacks=[CommandHandler("start", add_payer_start)],
)
