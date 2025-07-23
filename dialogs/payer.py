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
    BIRTH_DATE, EDIT_SELECT, EDIT_VALUE
) = range(21)

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

# === Додавання пайовика (кроки - як у всіх попередніх версіях) ===
# ... якщо треба - скину також усі кроки додавання, тут вони не змінювались ...

# === Список, картка, видалення, пошук ===

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
    return EDIT_SELECT

async def delete_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    del_query = Payer.delete().where(Payer.c.id == payer_id)
    await database.execute(del_query)
    await query.answer("Пайовика видалено!")
    await query.message.edit_text("Пайовика видалено.")
    return ConversationHandler.END

async def payer_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ID, ПІБ, ІПН або телефон пайовика:")

async def payer_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    results = []
    found_ids = set()
    if q.isdigit():
        res = await database.fetch_all(Payer.select().where(Payer.c.id == int(q)))
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    if re.fullmatch(r"\d{10}", q):
        res = await database.fetch_all(Payer.select().where(Payer.c.ipn == q))
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    if re.fullmatch(r"(\+380|0)\d{9}", q):
        phone = normalize_phone(q)
        res = await database.fetch_all(Payer.select().where(Payer.c.phone == phone))
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    if not results:
        res = await database.fetch_all(Payer.select().where(Payer.c.name.ilike(f"%{q}%")))
        results.extend([r for r in res if r.id not in found_ids])
    if not results:
        await update.message.reply_text("Пайовика не знайдено.")
        return
    for p in results:
        btn = InlineKeyboardButton(f"Картка", callback_data=f"payer_card:{p.id}")
        await update.message.reply_text(
            f"{p.id}. {p.name} (ІПН: {p.ipn})",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )

# === РЕДАГУВАННЯ: ізольовано і безпомилково ===

async def edit_payer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    context.user_data["edit_payer_id"] = payer_id
    keyboard = [
        [InlineKeyboardButton(field_name, callback_data=f"edit_field:{payer_id}:{field_key}")]
        for field_key, field_name in FIELDS
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"payer_card:{payer_id}")])
    await query.message.edit_text("Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_SELECT

async def edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, payer_id, field_key = query.data.split(":")
    payer_id = int(payer_id)
    context.user_data["edit_payer_id"] = payer_id
    context.user_data["edit_field"] = field_key
    select = Payer.select().where(Payer.c.id == payer_id)
    payer = await database.fetch_one(select)
    if not payer:
        await query.answer("Пайовик не знайдений!")
        return ConversationHandler.END
    old_value = getattr(payer, field_key, "")
    await query.message.edit_text(
        f"Поточне значення: <b>{old_value if old_value else '(порожньо)'}</b>\n"
        f"Введіть нове значення для поля: {dict(FIELDS)[field_key]}",
        parse_mode=ParseMode.HTML
    )
    return EDIT_VALUE

async def edit_field_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    payer_id = context.user_data.get("edit_payer_id")
    field_key = context.user_data.get("edit_field")
    if not payer_id or not field_key:
        await update.message.reply_text("⚠️ Технічна помилка! payer_id або поле не задано.")
        return ConversationHandler.END

    # Валідація формату для кожного поля (як при додаванні)
    if field_key == "ipn" and not is_ipn(value):
        await update.message.reply_text("ІПН має бути 10 цифр. Введіть ще раз:")
        return EDIT_VALUE
    if field_key == "phone":
        value = normalize_phone(value)
        if not value:
            await update.message.reply_text("Телефон має бути у форматі +380XXXXXXXXX або 0XXXXXXXXXX. Введіть ще раз:")
            return EDIT_VALUE
    if field_key == "passport_series" and not is_pass_series(value.upper()):
        await update.message.reply_text("Серія паспорта має бути 2 літери. Введіть ще раз:")
        return EDIT_VALUE
    if field_key == "passport_number" and not is_pass_number(value):
        await update.message.reply_text("Номер паспорта має бути 6 цифр. Введіть ще раз:")
        return EDIT_VALUE
    if field_key == "unzr" and not is_unzr(value):
        await update.message.reply_text("Формат УНЗР: 12345678-12345. Введіть ще раз:")
        return EDIT_VALUE
    if field_key == "id_number" and not is_idcard_number(value):
        await update.message.reply_text("Номер ID-картки має бути 9 цифр. Введіть ще раз:")
        return EDIT_VALUE
    if field_key == "idcard_issuer" and not is_idcard_issuer(value):
        await update.message.reply_text("Код підрозділу має бути 4 цифри. Введіть ще раз:")
        return EDIT_VALUE
    if field_key in ("passport_date", "idcard_date", "birth_date") and not is_date(value):
        await update.message.reply_text("Формат дати: дд.мм.рррр. Введіть ще раз:")
        return EDIT_VALUE

    # Оновлення в БД
    query_db = Payer.update().where(Payer.c.id == payer_id).values({field_key: value})
    await database.execute(query_db)
    await update.message.reply_text("✅ Зміни збережено!")
    # Повернутись до меню редагування
    return await edit_payer_menu_from_save(update, context)

async def edit_payer_menu_from_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payer_id = context.user_data.get("edit_payer_id")
    if not payer_id:
        await update.message.reply_text("⚠️ Технічна помилка! payer_id не задано.")
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton(field_name, callback_data=f"edit_field:{payer_id}:{field_key}")]
        for field_key, field_name in FIELDS
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"payer_card:{payer_id}")])
    await update.message.reply_text("Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_SELECT

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
        EDIT_SELECT: [
            CallbackQueryHandler(edit_field_input, pattern=r"^edit_field:\d+:\w+$"),
            CallbackQueryHandler(edit_payer_menu, pattern=r"^edit_payer:\d+$"),
            CallbackQueryHandler(payer_card, pattern=r"^payer_card:\d+$"),
            CallbackQueryHandler(delete_payer, pattern=r"^delete_payer:\d+$"),
        ],
        EDIT_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_save),
        ],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
