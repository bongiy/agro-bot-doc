import os
import unicodedata
import re

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, InputFile
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
)
from telegram.constants import ParseMode
from db import database, Payer, UploadedDocs
from dialogs.post_creation import prompt_add_docs
from keyboards.menu import payers_menu, main_menu
from ftp_utils import download_file_ftp, delete_file_ftp

import re
import sqlalchemy
(
    FIO, IPN, OBLAST, RAYON, SELO, VUL, BUD, KV,
    PHONE, DOC_TYPE,
    PASS_SERIES, PASS_NUMBER, PASS_ISSUER, PASS_DATE,
    IDCARD_NUMBER, IDCARD_UNZR, IDCARD_ISSUER, IDCARD_DATE,
    BIRTH_DATE
) = range(19)

# Клавіатури для кроків діалогу:
doc_type_keyboard = ReplyKeyboardMarkup(
    [["Паспорт (книжка)", "ID картка"]],
    resize_keyboard=True
)
oblast_keyboard = ReplyKeyboardMarkup(
    [["Рівненська", "Інша"], ["❌ Скасувати"]],
    resize_keyboard=True
)
rayon_keyboard = ReplyKeyboardMarkup(
    [["Рівненський", "Дубенський", "Інший"], ["◀️ Назад", "❌ Скасувати"]],
    resize_keyboard=True
)
back_cancel_keyboard = ReplyKeyboardMarkup(
    [["◀️ Назад", "❌ Скасувати"]],
    resize_keyboard=True
)

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
def to_latin_filename(text, default="document.pdf"):
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = name.replace(" ", "_")
    name = re.sub(r'[^A-Za-z0-9_.-]', '', name)
    if not name or name.startswith(".pdf") or name.lower() == ".pdf":
        return default
    if not name.lower().endswith('.pdf'):
        name += ".pdf"
    return name
# ==== ДОДАВАННЯ ПАЙОВИКА ====
async def back_or_cancel(update, context, step_back):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Додавання скасовано.", reply_markup=payers_menu)
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
    result = await back_or_cancel(update, context, IPN)
    if result is not None:
        return result
    text = update.message.text
    if text == "Інша":
        await update.message.reply_text("Введіть назву області:", reply_markup=back_cancel_keyboard)
        return OBLAST
    context.user_data["oblast"] = text
    await update.message.reply_text("Оберіть район:", reply_markup=rayon_keyboard)
    return RAYON

async def add_payer_rayon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, OBLAST)
    if result is not None:
        return result
    text = update.message.text
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

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Створити договір оренди", callback_data=f"create_contract:{payer_id}")],
        [InlineKeyboardButton("До меню", callback_data="to_menu")],
    ])
    final_text = "✅ Пайовика додано!"

    context.user_data.clear()
    await prompt_add_docs(
        update,
        context,
        "payer_passport" if d.get("doc_type") == "passport" else "payer_id",
        payer_id,
        final_text,
        keyboard,
    )
    return ConversationHandler.END

# ==== СПИСОК, КАРТКА, РЕДАГУВАННЯ, ВИДАЛЕННЯ ====
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

from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler
import sqlalchemy
from db import database, Payer, UploadedDocs

async def payer_card(update, context):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    select = Payer.select().where(Payer.c.id == payer_id)
    payer = await database.fetch_one(select)
    if not payer:
        await query.answer("Пайовик не знайдений!")
        return ConversationHandler.END

    text = (
        f"<b>{payer.name}</b>\n"
        f"🆔 ID: {payer.id}\n"
        f"📇 ІПН: {payer.ipn}\n"
        f"🎂 Дата народження: {payer.birth_date}\n"
        f"📞 Телефон: {payer.phone}\n"
        f"📑 Тип документа: {payer.doc_type}\n"
        f"🛂 Паспорт/ID: {payer.passport_series or ''} {payer.passport_number or ''} {payer.id_number or ''}\n"
        f"Ким виданий: {payer.passport_issuer or payer.idcard_issuer or ''}\n"
        f"Коли виданий: {payer.passport_date or payer.idcard_date or ''}\n"
        f"УНЗР: {payer.unzr or '-'}\n"
        f"🏠 Адреса: {payer.oblast} обл., {payer.rayon} р-н, с. {payer.selo}, вул. {payer.vul}, буд. {payer.bud}, кв. {payer.kv}"
    )

    keyboard = []

    # Визначаємо тип документу (entity_type) для пайовика: паспорт чи ID
    payer_doc_type = "payer_passport" if payer.doc_type == "passport" else "payer_id"
    
    # --- Кнопка "Додати документи" (перша, завжди) ---
    keyboard.append([
        InlineKeyboardButton(
            "📷 Додати документи", callback_data=f"add_docs:{payer_doc_type}:{payer.id}"
        )
    ])

    # --- Кнопки перегляду/видалення PDF по назві документу ---
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs)
        .where((UploadedDocs.c.entity_type == payer_doc_type) & (UploadedDocs.c.entity_id == payer.id))
    )
    for doc in docs:
        doc_type = doc['doc_type']
        keyboard.append([
            InlineKeyboardButton(f"⬇️ {doc_type}", callback_data=f"send_pdf:{doc['id']}"),
            InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_pdf_db:{doc['id']}")
        ])

    # --- Інші функціональні кнопки ---
    keyboard.extend([
        [InlineKeyboardButton("Редагувати", callback_data=f"edit_payer:{payer.id}")],
        [InlineKeyboardButton("Видалити", callback_data=f"delete_payer:{payer.id}")],
        [InlineKeyboardButton("Створити договір оренди", callback_data=f"create_contract:{payer.id}")],
        [InlineKeyboardButton("До меню", callback_data="to_menu")]
    ])

    await query.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# ==== СКАЧУВАННЯ PDF через FTP ====
async def send_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        remote_path = row['remote_path']
        filename = to_latin_filename(remote_path.split('/')[-1])
        tmp_path = f"temp_docs/{filename}"
        try:
            os.makedirs("temp_docs", exist_ok=True)
            download_file_ftp(remote_path, tmp_path)
            await query.message.reply_document(document=InputFile(tmp_path), filename=filename)
            os.remove(tmp_path)
        except Exception as e:
            await query.answer(f"Помилка при скачуванні файлу: {e}", show_alert=True)
    else:
        await query.answer("Документ не знайдено!", show_alert=True)

async def delete_payer_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    from db import get_user_by_tg_id
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    payer = await database.fetch_one(Payer.select().where(Payer.c.id == payer_id))
    if not payer:
        await query.answer("Пайовика не знайдено!", show_alert=True)
        return
    text = (
        f"Ви точно хочете видалити <b>{payer.name}</b>?\n"
        "Цю дію не можна скасувати."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_delete_payer:{payer_id}")],
        [InlineKeyboardButton("❌ Скасувати", callback_data=f"payer_card:{payer_id}")],
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

async def delete_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    from db import LandPlot, UploadedDocs, get_user_by_tg_id, log_delete
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    payer = await database.fetch_one(Payer.select().where(Payer.c.id == payer_id))
    if not payer:
        await query.answer("Пайовика не знайдено!", show_alert=True)
        return
    linked_lands = await database.fetch_all(
        sqlalchemy.select(LandPlot).where(LandPlot.c.payer_id == payer_id)
    )
    if linked_lands:
        await query.answer("Не можна видалити — до пайовика прив'язані ділянки.", show_alert=True)
        return
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs).where(
            (UploadedDocs.c.entity_id == payer_id) &
            (UploadedDocs.c.entity_type.in_(["payer_passport", "payer_id"]))
        )
    )
    for d in docs:
        try:
            delete_file_ftp(d["remote_path"])
        except Exception:
            pass
    if docs:
        await database.execute(
            UploadedDocs.delete().where(UploadedDocs.c.id.in_([d["id"] for d in docs]))
        )
    await database.execute(Payer.delete().where(Payer.c.id == payer_id))
    linked = f"docs:{len(docs)}" if docs else ""
    await log_delete(update.effective_user.id, user["role"], "payer", payer_id, payer.name, linked)
    await query.message.edit_text("✅ Обʼєкт успішно видалено")
    return ConversationHandler.END

async def create_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    await query.answer()
    await query.message.reply_text(f"🔜 Функція створення договору в розробці!\nПайовик #{payer_id}")

async def to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.reply_text("Головне меню:", reply_markup=main_menu)
    return ConversationHandler.END

add_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати пайовика$"), add_payer_start)],
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
