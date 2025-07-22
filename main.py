import os
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    filters,
)
from telegram.constants import ParseMode

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Меню-клавіатура
menu_keyboard = ReplyKeyboardMarkup(
    [
        ["Новий пайовик", "Додати ділянку"],
        ["Таблиця виплат", "Довідка"],
    ],
    resize_keyboard=True
)

# FastAPI app
app = FastAPI()

# Telegram PTB Application
application = Application.builder().token(TOKEN).build()

# Стартова команда — показує меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вітаємо! Оберіть дію:",
        reply_markup=menu_keyboard
    )

# Обробка натискання кнопок меню
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Новий пайовик":
        await update.message.reply_text("Введіть ПІБ пайовика…")
    elif text == "Додати ділянку":
        await update.message.reply_text("Введіть дані по ділянці…")
    elif text == "Таблиця виплат":
        await update.message.reply_text("Ось ваша таблиця виплат…")
    elif text == "Довідка":
        await update.message.reply_text("Довідка по функціях бота…")
    else:
        await update.message.reply_text("Оберіть дію з меню нижче.", reply_markup=menu_keyboard)

# Додаємо хендлери до PTB Application
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT, menu_handler))

# FastAPI endpoint для webhook
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

# Webhook setup при старті
@app.on_event("startup")
async def on_startup():
    await application.bot.set_webhook(WEBHOOK_URL)

# Для локального тесту (з uvicorn або hypercorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
