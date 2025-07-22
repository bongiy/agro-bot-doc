import os
import re
from fastapi import FastAPI, Request
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
)

# ======= Константи етапів анкети пайовика =======
(
    FIO, IPN, ADDRESS, PHONE, DOC_TYPE,
    PASS_SERIES, PASS_NUMBER, PASS_ISSUER, PASS_DATE,
    IDCARD_NUMBER, IDCARD_UNZR, IDCARD_ISSUER, IDCARD_DATE,
    BIRTH_DATE
) = range(14)

menu_keyboard = ReplyKeyboardMarkup(
    [
        ["Новий пайовик", "Додати ділянку"],
        ["Таблиця виплат", "Довідка"],
    ],
    resize_keyboard=True
)

doc_type_keyboard = ReplyKeyboardMarkup(
    [["Паспорт (книжка)", "ID картка"]], resize_keyboard=True
)

# ======= Валідаційні функції =======
def is_ipn(text): return re.fullmatch(r"\d{10}", text)
def is_phone(text): return re.fullmatch(r"\+380\d{9}", text)
def is_pass_series(text): return re.fullmatch(r"[A-ZА-ЯІЇЄҐ]{2}", text)
def is_pass_number(text): return re.fullmatch(r"\d{6}", text)
def is_unzr(text): return re.fullmatch(r"\d{8}-\d{5}", text)
def is_idcard_number(text): return re.fullmatch(r"\d{9}", text)
def is_idcard_issuer(text): return re.fullmatch(r"\d{4}", text)
def is_date(text): return re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text)

# ======= "База" пайовиків (тимчасово у памʼяті) =======
payers = {}

# ======= FastAPI та Telegram Application =======
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()
application = Application.builder().token(TOKEN).build()
is_initialized = False

@app.on_event("startup")
async def on_startup():
    global is_initialized
    if not is_initialized:
        await application.initialize()
        await application.bot.set_webhook(WEBHOOK_URL)
        is_initialized = True

# ======= Меню-стартер =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вітаємо! Оберіть дію:", reply_markup=menu_keyboard
    )

# ======= ConversationHandler для пайовика =======
async def add_payer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Введіть ПІБ пайовика:", reply_markup=ReplyKeyboardRemove())
    return FIO

async def add_payer_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Введіть ІПН (10 цифр):")
    return IPN

async def add_payer_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_ipn(update.message.text):
        await update.message.reply_text("❗️ ІПН має бути 10 цифр. Спробуйте ще раз:")
        return IPN
    context.user_data["ipn"] = update.message.text
    await update.message.reply_text("Введіть адресу (ОБЛАСТЬ, РАЙОН, СЕЛО, ВУЛИЦЯ, №, КВАРТИРА):")
    return ADDRESS

async def add_payer_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text("Введіть номер телефону у форматі +380XXXXXXXXX:")
    return PHONE

async def add_payer_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_phone(update.message.text):
        await update.message.reply_text("❗️ Формат телефону: +380XXXXXXXXX. Спробуйте ще раз:")
        return PHONE
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("Оберіть тип документа:", reply_markup=doc_type_keyboard)
    return DOC_TYPE

async def add_payer_doc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Паспорт (книжка)":
        context.user_data["doc_type"] = "passport"
        await update.message.reply_text("Введіть серію паспорта (2 літери):", reply_markup=ReplyKeyboardRemove())
        return PASS_SERIES
    elif text == "ID картка":
        context.user_data["doc_type"] = "id_card"
        await update.message.reply_text("Введіть номер ID-картки (9 цифр):", reply_markup=ReplyKeyboardRemove())
        return IDCARD_NUMBER
    else:
        await update.message.reply_text("❗️ Оберіть тип документа через кнопки нижче:", reply_markup=doc_type_keyboard)
        return DOC_TYPE

# ---- Паспорт
async def add_payer_pass_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_pass_series(update.message.text.upper()):
        await update.message.reply_text("❗️ Серія — це 2 літери (наприклад, АА).")
        return PASS_SERIES
    context.user_data["passport_series"] = update.message.text.upper()
    await update.message.reply_text("Введіть номер паспорта (6 цифр):")
    return PASS_NUMBER

async def add_payer_pass_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_pass_number(update.message.text):
        await update.message.reply_text("❗️ Номер паспорта — 6 цифр.")
        return PASS_NUMBER
    context.user_data["passport_number"] = update.message.text
    await update.message.reply_text("Введіть, ким виданий паспорт:")
    return PASS_ISSUER

async def add_payer_pass_issuer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["passport_issuer"] = update.message.text
    await update.message.reply_text("Введіть дату видачі паспорта (дд.мм.рррр):")
    return PASS_DATE

async def add_payer_pass_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return PASS_DATE
    context.user_data["passport_date"] = update.message.text
    await update.message.reply_text("Введіть дату народження пайовика (дд.мм.рррр):")
    return BIRTH_DATE

# ---- ID-картка
async def add_payer_idcard_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_idcard_number(update.message.text):
        await update.message.reply_text("❗️ Номер ID-картки — 9 цифр.")
        return IDCARD_NUMBER
    context.user_data["id_number"] = update.message.text
    await update.message.reply_text("Введіть номер запису УНЗР (8 цифр-5 цифр):")
    return IDCARD_UNZR

async def add_payer_idcard_unzr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_unzr(update.message.text):
        await update.message.reply_text("❗️ Формат УНЗР: 12345678-12345.")
        return IDCARD_UNZR
    context.user_data["unzr"] = update.message.text
    await update.message.reply_text("Введіть код підрозділу, ким видано ID (4 цифри):")
    return IDCARD_ISSUER

async def add_payer_idcard_issuer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_idcard_issuer(update.message.text):
        await update.message.reply_text("❗️ Код підрозділу — 4 цифри.")
        return IDCARD_ISSUER
    context.user_data["idcard_issuer"] = update.message.text
    await update.message.reply_text("Введіть дату видачі ID-картки (дд.мм.рррр):")
    return IDCARD_DATE

async def add_payer_idcard_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return IDCARD_DATE
    context.user_data["idcard_date"] = update.message.text
    await update.message.reply_text("Введіть дату народження пайовика (дд.мм.рррр):")
    return BIRTH_DATE

# ---- Завершення анкети
async def add_payer_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return BIRTH_DATE
    context.user_data["birth_date"] = update.message.text
    user_id = update.message.from_user.id
    payers.setdefault(user_id, []).append(context.user_data.copy())
    await update.message.reply_text(
        f"✅ Пайовика додано!\n\nДані:\n{context.user_data}\n\n/start — в меню.",
        reply_markup=menu_keyboard
    )
    return ConversationHandler.END

add_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Новий пайовик$"), add_payer_start)],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_fio)],
        IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_ipn)],
        ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_address)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_phone)],
        DOC_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_doc_type)],
        PASS_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_series)],
        PASS_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_number)],
        PASS_ISSUER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_issuer)],
        PASS_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_date)],
        IDCARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_number)],
        IDCARD_UNZR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_unzr)],
        IDCARD_ISSUER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_issuer)],
        IDCARD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_date)],
        BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_birth_date)],
    },
    fallbacks=[CommandHandler("start", add_payer_start)],
)

# ======= Меню/інші функції =======
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Додати ділянку":
        await update.message.reply_text("Введіть дані по ділянці… (функція у розробці)")
    elif text == "Таблиця виплат":
        await update.message.reply_text("Ось ваша таблиця виплат… (функція у розробці)")
    elif text == "Довідка":
        await update.message.reply_text("Довідка по функціях бота…")
    else:
        await update.message.reply_text("Оберіть дію з меню нижче.", reply_markup=menu_keyboard)

# ======= Додаємо хендлери =======
application.add_handler(CommandHandler("start", start))
application.add_handler(add_payer_conv)
application.add_handler(MessageHandler(filters.TEXT, menu_handler))

# ======= Webhook endpoint =======
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

# ======= Локальний запуск (тільки для тесту) =======
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
