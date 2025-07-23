from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters
)
from telegram.constants import ParseMode
from db import database, Payer

import re

(
    FIO, IPN, OBLAST, RAYON, SELO, VUL, BUD, KV,
    PHONE, DOC_TYPE,
    PASS_SERIES, PASS_NUMBER, PASS_ISSUER, PASS_DATE,
    IDCARD_NUMBER, IDCARD_UNZR, IDCARD_ISSUER, IDCARD_DATE,
    BIRTH_DATE
) = range(19)

menu_keyboard = ReplyKeyboardMarkup(
    [
        ["Новий пайовик", "Список пайовиків"],
        ["Пошук пайовика"],
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

FIELDS = [
    ("name", "ПІБ"),
    ("ipn", "ІПН"),
    ("oblast", "Область"),
    ("rayon", "Район"),
    ("selo", "Село"),
    ("vul", "Вулиця"),
    ("bud", "Будинок"),
    ("kv", "Квартира"),
    ("phone", "Телефон"),
    ("doc_type", "Тип документа"),
    ("passport_series", "Серія паспорта"),
    ("passport_number", "Номер паспорта"),
    ("passport_issuer", "Ким виданий"),
    ("passport_date", "Коли виданий"),
    ("id_number", "ID-картка"),
    ("unzr", "УНЗР"),
    ("idcard_issuer", "Код підрозділу"),
    ("idcard_date", "Дата видачі ID"),
    ("birth_date", "Дата народження"),
]
allowed_fields = [f[0] for f in FIELDS]

def is_ipn(text): return re.fullmatch(r"\d{10}", text)
def is_pass_series(text): return re.fullmatch(r"[A-ZА-ЯІЇЄҐ]{2}", text)
def is_pass_number(text): return re.fullmatch(r"\d{6}", text)
def is_unzr(text): return re.fullmatch(r"\d{8}-\d{5}", text)
def is_idcard_number(text): return re.fullmatch(r"\d{9}", text)
def is_idcard_issuer(text): return re.fullmatch(r"\d{4}", text)
def is_date(text): return re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text)
def normalize_phone(text):
    text = text.strip().replace(" ", "").replace("-", "")
    if re.fullmatch(r"0\d{9}", text):
        return "+38" + text
    if re.fullmatch(r"\+380\d{9}", text):
        return text
    return None

# ==== ДОДАВАННЯ ПАЙОВИКА ====
async def back_or_cancel(update, context, step_back):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Додавання скасовано.", reply_markup=menu_keyboard)
        context.user_data.clear()
        return ConversationHandler.END
    if text == "◀️ Назад":
        return step_back
    return None

async def add_payer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Введіть ПІБ пайовика:",
        reply_markup=back_cancel_keyboard
    )
    return FIO

async def add_payer_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, FIO)
    if result is not None:
        return result
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Введіть ІПН (10 цифр):",
        reply_markup=back_cancel_keyboard
    )
    return IPN

async def add_payer_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, FIO)
    if result is not None:
        return result
    if not is_ipn(update.message.text):
        await update.message.reply_text("❗️ ІПН має бути 10 цифр. Спробуйте ще раз:")
        return IPN
    context.user_data["ipn"] = update.message.text
    await update.message.reply_text(
        "Оберіть область:", reply_markup=oblast_keyboard
    )
    return OBLAST

async def add_payer_oblast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Додавання скасовано.", reply_markup=menu_keyboard)
        context.user_data.clear()
        return ConversationHandler.END
    if text == "Інша":
        await update.message.reply_text("Введіть назву області:", reply_markup=back_cancel_keyboard)
        return OBLAST
    context.user_data["oblast"] = text
    await update.message.reply_text("Оберіть район:", reply_markup=rayon_keyboard)
    return RAYON

async def add_payer_rayon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Додавання скасовано.", reply_markup=menu_keyboard)
        context.user_data.clear()
        return ConversationHandler.END
    if text == "◀️ Назад":
        await update.message.reply_text("Оберіть область:", reply_markup=oblast_keyboard)
        return OBLAST
    if text == "Інший":
        await update.message.reply_text("Введіть назву району:", reply_markup=back_cancel_keyboard)
        return RAYON
    context.user_data["rayon"] = text
    await update.message.reply_text("Введіть назву села:", reply_markup=back_cancel_keyboard)
    return SELO

async def add_payer_selo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, RAYON)
    if result is not None:
        return result
    context.user_data["selo"] = update.message.text
    await update.message.reply_text("Введіть назву вулиці:", reply_markup=back_cancel_keyboard)
    return VUL

async def add_payer_vul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, SELO)
    if result is not None:
        return result
    context.user_data["vul"] = update.message.text
    await update.message.reply_text("Введіть номер будинку:", reply_markup=back_cancel_keyboard)
    return BUD

async def add_payer_bud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, VUL)
    if result is not None:
        return result
    context.user_data["bud"] = update.message.text
    await update.message.reply_text("Введіть номер квартири (або '-' якщо немає):", reply_markup=back_cancel_keyboard)
    return KV

async def add_payer_kv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, BUD)
    if result is not None:
        return result
    context.user_data["kv"] = update.message.text
    await update.message.reply_text(
        "Введіть номер телефону у форматі +380XXXXXXXXX або 0XXXXXXXXXX:",
        reply_markup=back_cancel_keyboard
    )
    return PHONE

async def add_payer_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, KV)
    if result is not None:
        return result
    phone = normalize_phone(update.message.text)
    if not phone:
        await update.message.reply_text("❗️ Введіть номер у форматі +380XXXXXXXXX або 0XXXXXXXXXX")
        return PHONE
    context.user_data["phone"] = phone
    await update.message.reply_text("Оберіть тип документа:", reply_markup=doc_type_keyboard)
    return DOC_TYPE

async def add_payer_doc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Паспорт (книжка)":
        context.user_data["doc_type"] = "passport"
        await update.message.reply_text("Введіть серію паспорта (2 літери):", reply_markup=back_cancel_keyboard)
        return PASS_SERIES
    elif text == "ID картка":
        context.user_data["doc_type"] = "id_card"
        await update.message.reply_text("Введіть номер ID-картки (9 цифр):", reply_markup=back_cancel_keyboard)
        return IDCARD_NUMBER
    else:
        await update.message.reply_text("❗️ Оберіть тип документа через кнопки:", reply_markup=doc_type_keyboard)
        return DOC_TYPE
async def add_payer_pass_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, DOC_TYPE)
    if result is not None:
        return result
    if not is_pass_series(update.message.text.upper()):
        await update.message.reply_text("❗️ Серія — це 2 літери (наприклад, АА).")
        return PASS_SERIES
    context.user_data["passport_series"] = update.message.text.upper()
    await update.message.reply_text("Введіть номер паспорта (6 цифр):", reply_markup=back_cancel_keyboard)
    return PASS_NUMBER

async def add_payer_pass_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_SERIES)
    if result is not None:
        return result
    if not is_pass_number(update.message.text):
        await update.message.reply_text("❗️ Номер паспорта — 6 цифр.")
        return PASS_NUMBER
    context.user_data["passport_number"] = update.message.text
    await update.message.reply_text("Введіть, ким виданий паспорт:", reply_markup=back_cancel_keyboard)
    return PASS_ISSUER

async def add_payer_pass_issuer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_NUMBER)
    if result is not None:
        return result
    context.user_data["passport_issuer"] = update.message.text
    await update.message.reply_text("Введіть дату видачі паспорта (дд.мм.рррр):", reply_markup=back_cancel_keyboard)
    return PASS_DATE

async def add_payer_pass_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_ISSUER)
    if result is not None:
        return result
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return PASS_DATE
    context.user_data["passport_date"] = update.message.text
    await update.message.reply_text("Введіть дату народження пайовика (дд.мм.рррр):", reply_markup=back_cancel_keyboard)
    return BIRTH_DATE

async def add_payer_idcard_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, DOC_TYPE)
    if result is not None:
        return result
    if not is_idcard_number(update.message.text):
        await update.message.reply_text("❗️ Номер ID-картки — 9 цифр.")
        return IDCARD_NUMBER
    context.user_data["id_number"] = update.message.text
    await update.message.reply_text("Введіть номер запису УНЗР (8 цифр-5 цифр):", reply_markup=back_cancel_keyboard)
    return IDCARD_UNZR

async def add_payer_idcard_unzr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, IDCARD_NUMBER)
    if result is not None:
        return result
    if not is_unzr(update.message.text):
        await update.message.reply_text("❗️ Формат УНЗР: 12345678-12345.")
        return IDCARD_UNZR
    context.user_data["unzr"] = update.message.text
    await update.message.reply_text("Введіть код підрозділу, ким видано ID (4 цифри):", reply_markup=back_cancel_keyboard)
    return IDCARD_ISSUER

async def add_payer_idcard_issuer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, IDCARD_UNZR)
    if result is not None:
        return result
    if not is_idcard_issuer(update.message.text):
        await update.message.reply_text("❗️ Код підрозділу — 4 цифри.")
        return IDCARD_ISSUER
    context.user_data["idcard_issuer"] = update.message.text
    await update.message.reply_text("Введіть дату видачі ID-картки (дд.мм.рррр):", reply_markup=back_cancel_keyboard)
    return IDCARD_DATE

async def add_payer_idcard_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, IDCARD_ISSUER)
    if result is not None:
        return result
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return IDCARD_DATE
    context.user_data["idcard_date"] = update.message.text
    await update.message.reply_text("Введіть дату народження пайовика (дд.мм.рррр):", reply_markup=back_cancel_keyboard)
    return BIRTH_DATE

async def add_payer_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_DATE if context.user_data.get("doc_type") == "passport" else IDCARD_DATE)
    if result is not None:
        return result
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return BIRTH_DATE
    context.user_data["birth_date"] = update.message.text
    d = context.user_data
    query = Payer.insert().values(
        name=d.get("name"),
        ipn=d.get("ipn"),
        oblast=d.get("oblast"),
        rayon=d.get("rayon"),
        selo=d.get("selo"),
        vul=d.get("vul"),
        bud=d.get("bud"),
        kv=d.get("kv"),
        phone=d.get("phone"),
        doc_type=d.get("doc_type"),
        passport_series=d.get("passport_series"),
        passport_number=d.get("passport_number"),
        passport_issuer=d.get("passport_issuer"),
        passport_date=d.get("passport_date"),
        id_number=d.get("id_number"),
        unzr=d.get("unzr"),
        idcard_issuer=d.get("idcard_issuer"),
        idcard_date=d.get("idcard_date"),
        birth_date=d.get("birth_date"),
    )
    payer_id = await database.execute(query)
    keyboard = [
        [InlineKeyboardButton("Створити договір оренди", callback_data=f"create_contract:{payer_id}")],
        [InlineKeyboardButton("До меню", callback_data="to_menu")]
    ]
    await update.message.reply_text(
        f"✅ Пайовика додано!", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.clear()
    return ConversationHandler.END

# ==== СПИСОК, КАРТКА, ПОШУК, РЕДАГУВАННЯ, ВИДАЛЕННЯ ====
async def show_payers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = Payer.select()
    payers = await database.fetch_all(query)
    if not payers:
        await update.message.reply_text("Список порожній!")
        return
    for p in payers:
        button = InlineKeyboardButton(f"Картка", callback_data=f"payer_card:{p.id}")
        await update.message.reply_text(
            f"{p.id}. {p.name} (ІПН: {p.ipn})",
            reply_markup=InlineKeyboardMarkup([[button]])
        )

async def payer_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    select = Payer.select().where(Payer.c.id == payer_id)
    payer = await database.fetch_one(select)
    if not payer:
        await query.answer("Пайовик не знайдений!")
        return ConversationHandler.END
    text = f"""<b>Картка пайовика</b>
ID: {payer.id}
ПІБ: {payer.name}
ІПН: {payer.ipn}
Адреса: {payer.oblast} обл., {payer.rayon} р-н, с. {payer.selo}, вул. {payer.vul}, буд. {payer.bud}, кв. {payer.kv}
Телефон: {payer.phone}
Тип документа: {payer.doc_type}
Паспорт/ID: {payer.passport_series or ''} {payer.passport_number or ''} {payer.id_number or ''}
Ким виданий: {payer.passport_issuer or payer.idcard_issuer or ''}
Коли виданий: {payer.passport_date or payer.idcard_date or ''}
УНЗР: {payer.unzr or '-'}
Дата народження: {payer.birth_date}
"""
    keyboard = [
        [InlineKeyboardButton("Редагувати", callback_data=f"edit_payer:{payer.id}")],
        [InlineKeyboardButton("Видалити", callback_data=f"delete_payer:{payer.id}")],
        [InlineKeyboardButton("Створити договір оренди", callback_data=f"create_contract:{payer.id}")],
        [InlineKeyboardButton("До меню", callback_data="to_menu")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def delete_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    del_query = Payer.delete().where(Payer.c.id == payer_id)
    await database.execute(del_query)
    await query.answer("Пайовика видалено!")
    await query.message.edit_text("Пайовика видалено.")
    return ConversationHandler.END

async def create_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    await query.answer()
    await query.message.reply_text(f"🔜 Функція створення договору в розробці!\nПайовик #{payer_id}")

async def to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.reply_text("Головне меню:", reply_markup=menu_keyboard)
    return ConversationHandler.END

add_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Новий пайовик$"), add_payer_start)],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_fio)],
        IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_ipn)],
        OBLAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_oblast)],
        RAYON: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_rayon)],
        SELO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_selo)],
        VUL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_vul)],
        BUD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_bud)],
        KV: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_kv)],
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
    fallbacks=[CommandHandler("start", to_menu)],
)
