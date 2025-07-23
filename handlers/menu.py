from telegram import Update
from telegram.ext import ContextTypes
from keyboards.menu import main_menu, payers_menu

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вітаємо! Головне меню:", reply_markup=main_menu)

async def to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Головне меню:", reply_markup=main_menu)

async def payers_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Пайовики»", reply_markup=payers_menu)
