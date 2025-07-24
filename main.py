import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ConversationHandler
)
from handlers.menu import (
    start, to_main_menu, payers_menu_handler, lands_menu_handler, fields_menu_handler,
    contracts_menu_handler, payments_menu_handler, reports_menu_handler, search_menu_handler, restart_bot
)

from dialogs.payer import (
    add_payer_conv, show_payers, payer_card, delete_payer,
    create_contract, to_menu
)
from dialogs.edit_payer import edit_payer_conv
from dialogs.search import search_payer_conv
from dialogs.field import add_field_conv, show_fields, delete_field
from dialogs.land import add_land_conv, show_lands, delete_land

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

# === Основні handlers ===

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Regex("^◀️ Назад$"), to_main_menu))
application.add_handler(MessageHandler(filters.Regex("^🔹 Пайовики$"), payers_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔹 Ділянки$"), lands_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔹 Поля$"), fields_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔹 Договори$"), contracts_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔹 Виплати$"), payments_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔹 Звіти$"), reports_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔹 Пошук$"), search_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔄 Перезавантажити$"), restart_bot))

# --- ПАЙОВИКИ: Підключаємо діалоги до підменю пайовиків
application.add_handler(add_payer_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список пайовиків$"), show_payers))
application.add_handler(search_payer_conv)
application.add_handler(edit_payer_conv)

# --- ДІЛЯНКИ/ПОЛЯ ---
application.add_handler(add_field_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список полів$"), show_fields))
application.add_handler(add_land_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список ділянок$"), show_lands))
application.add_handler(CallbackQueryHandler(delete_field, pattern=r"^delete_field:"))
application.add_handler(CallbackQueryHandler(delete_land, pattern=r"^delete_land:"))


# CallbackQueryHandler-и — як є, доки не переведені на нову систему:
application.add_handler(CallbackQueryHandler(payer_card, pattern=r"^payer_card:"))
application.add_handler(CallbackQueryHandler(delete_payer, pattern=r"^delete_payer:"))
application.add_handler(CallbackQueryHandler(to_menu, pattern=r"^to_menu$"))
application.add_handler(CallbackQueryHandler(create_contract, pattern=r"^create_contract:"))

# fallback: обробляємо всі невідомі команди поверненням у головне меню
application.add_handler(MessageHandler(filters.COMMAND, to_main_menu))

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
