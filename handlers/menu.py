from telegram import Update
from telegram.ext import ContextTypes
from keyboards.menu import (
    main_menu, payers_menu, lands_menu, fields_menu,
    contracts_menu, payments_menu, reports_menu, search_menu
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вітаємо! Головне меню:", reply_markup=main_menu)

async def to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Головне меню:", reply_markup=main_menu)

async def payers_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Пайовики»", reply_markup=payers_menu)
async def lands_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Ділянки»", reply_markup=lands_menu)

async def fields_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Поля»", reply_markup=fields_menu)

async def contracts_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Договори»", reply_markup=contracts_menu)

async def payments_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Виплати»", reply_markup=payments_menu)

async def reports_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Звіти»", reply_markup=reports_menu)

async def search_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Пошук»", reply_markup=search_menu)

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_ids = [123456789]  # заміни на свої user_id!
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("У вас немає прав для цієї дії.")
        return
    await update.message.reply_text("Бот буде перезавантажено...")
    import sys, os
    os.execl(sys.executable, sys.executable, *sys.argv)
