from telegram import Update
from telegram.ext import ContextTypes
from keyboards.menu import main_menu, main_menu_admin  # імпортуємо обидва меню

# TODO: Замініть цей список на актуальні admin_ids або імпортуйте з config
admin_ids = [123456789]  # <--- Вкажи свій Telegram user_id тут!

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in admin_ids
    await update.message.reply_text(
        "Вітаємо! Головне меню:",
        reply_markup=main_menu_admin if is_admin else main_menu
    )

async def to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in admin_ids
    await update.message.reply_text(
        "Головне меню:",
        reply_markup=main_menu_admin if is_admin else main_menu
    )

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

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("У вас немає прав для цієї дії.")
        return
    await update.message.reply_text(
        "🔐 <b>Адмінпанель</b>:\n\n"
        "• Менеджмент ТОВ-орендарів\n"
        "• Менеджмент шаблонів договорів\n"
        "• Менеджмент користувачів\n"
        "• Видалення пайовиків/полів/ділянок\n"
        "• Перезавантажити бот\n"
        "• ↩️ Повернутись",
        parse_mode="HTML"
    )

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("У вас немає прав для цієї дії.")
        return
    await update.message.reply_text("Бот буде перезавантажено...")
    import sys, os
    os.execl(sys.executable, sys.executable, *sys.argv)
