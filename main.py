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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

menu_keyboard = ReplyKeyboardMarkup(
    [
        ["Новий пайовик", "Додати ділянку"],
        ["Таблиця виплат", "Довідка"],
    ],
    resize_keyboard=True
)

app = FastAPI()
application = Application.builder().token(TOKEN).build()

# ---------------------------------------------
# Додаємо ПРАВИЛЬНУ ІНІЦІАЛІЗАЦІЮ тут!
is_initialized = False

@app.on_event("startup")
async def on_startup():
    global is_initialized
    if not is_initialized:
        await application.initialize()
        await application.bot.set_webhook(WEBHOOK_URL)
        is_initialized = True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вітаємо! Оберіть дію:",
        reply_markup=menu_keyboard
    )

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

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT, menu_handler))

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    # ----------- Перед обробкою переконаємось, що Application ініціалізовано! ----------
    global is_initialized
    if not is_initialized:
        await application.initialize()
        is_initialized = True
    # ---------------------------------------------------------------------------
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
