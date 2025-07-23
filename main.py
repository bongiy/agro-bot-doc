import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ConversationHandler
)
from dialogs.payer import (
    menu_keyboard, add_payer_conv, show_payers, payer_card, delete_payer,
    create_contract, to_menu
)
from dialogs.edit_payer import edit_payer_conv
from dialogs.search import search_payer_conv

# --- нові діалоги для полів і ділянок ---
from dialogs.field import add_field_conv, show_fields
from dialogs.land import add_land_conv, show_lands

from db import database

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()
application = Application.builder().token(TOKEN).build()
is_initialized = False

@app.on_event("startup")
async def on_startup():
    global is_initialized
    await database.connect()
    if not is_initialized:
        await application.initialize()
        await application.bot.set_webhook(WEBHOOK_URL)
        is_initialized = True

@app.on_event("shutdown")
async def on_shutdown():
    await database.disconnect()

async def start(update: Update, context):
    await update.message.reply_text("Вітаємо! Оберіть дію:", reply_markup=menu_keyboard)
    context.user_data.clear()

async def menu_handler(update: Update, context):
    await update.message.reply_text("Оберіть дію з меню нижче.", reply_markup=menu_keyboard)

# === Основні handlers ===

application.add_handler(CommandHandler("start", start))

application.add_handler(add_payer_conv)
application.add_handler(search_payer_conv)
application.add_handler(edit_payer_conv)
application.add_handler(MessageHandler(filters.Regex("^Список пайовиків$"), show_payers))

# --- НОВІ ХЕНДЛЕРИ ДЛЯ ПОЛІВ/ДІЛЯНОК ---
application.add_handler(add_field_conv)
application.add_handler(CommandHandler("fields", show_fields))
application.add_handler(add_land_conv)
application.add_handler(CommandHandler("lands", show_lands))

# CallbackQueryHandler-и:
application.add_handler(CallbackQueryHandler(payer_card, pattern=r"^payer_card:"))
application.add_handler(CallbackQueryHandler(delete_payer, pattern=r"^delete_payer:"))
application.add_handler(CallbackQueryHandler(to_menu, pattern=r"^to_menu$"))
application.add_handler(CallbackQueryHandler(create_contract, pattern=r"^create_contract:"))

# fallback:
application.add_handler(MessageHandler(filters.COMMAND, menu_handler))

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    global is_initialized
    if not is_initialized:
        await application.initialize()
        is_initialized = True
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
