import os
import unicodedata
import re

from telegram import (
    Update,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
from telegram.constants import ParseMode
from db import (
    database,
    Payer,
    UploadedDocs,
    Heir,
    InheritanceTransfer,
    LandPlot,
    Contract,
    InheritanceDebt,
    get_user_by_tg_id,
)
from dialogs.post_creation import prompt_add_docs
from keyboards.menu import payers_menu, main_menu, main_menu_admin
from ftp_utils import download_file_ftp, delete_file_ftp
from contract_generation_v2 import format_money

import re
import sqlalchemy
(
    FIO, IPN, OBLAST, RAYON, SELO, VUL, BUD, KV,
    PHONE, DOC_TYPE,
    PASS_SERIES, PASS_NUMBER, PASS_ISSUER, PASS_DATE,
    IDCARD_NUMBER, IDCARD_UNZR, IDCARD_ISSUER, IDCARD_DATE,
    BIRTH_DATE, BANK_CARD
) = range(20)

# Клавіатури для кроків діалогу:
doc_type_keyboard = ReplyKeyboardMarkup(
    [["Паспорт (книжка)", "ID картка"], ["◀️ Назад", "❌ Скасувати"]],
    resize_keyboard=True,
)
oblast_keyboard = ReplyKeyboardMarkup(
    [["Рівненська", "Інша"], ["◀️ Назад", "❌ Скасувати"]],
    resize_keyboard=True,
)
rayon_keyboard = ReplyKeyboardMarkup(
    [["Рівненський", "Дубенський", "Інший"], ["◀️ Назад", "❌ Скасувати"]],
    resize_keyboard=True
)
back_cancel_keyboard = ReplyKeyboardMarkup(
    [["◀️ Назад", "❌ Скасувати"]],
    resize_keyboard=True
)

SKIP_PREFIX = "skip"


async def prompt_step(msg, state: int):
    """Send prompt for the given FSM state with a skip button."""
    skip_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⏭ Пропустити", callback_data=f"{SKIP_PREFIX}:{state}")]]
    )
    if state == IPN:
        await msg.reply_text("Введіть ІПН (10 цифр):", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == OBLAST:
        await msg.reply_text("Оберіть область:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=oblast_keyboard)
    elif state == RAYON:
        await msg.reply_text("Оберіть район:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=rayon_keyboard)
    elif state == SELO:
        await msg.reply_text("Введіть назву села:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == VUL:
        await msg.reply_text("Введіть назву вулиці:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == BUD:
        await msg.reply_text("Введіть номер будинку:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == KV:
        await msg.reply_text(
            "Введіть номер квартири (або '-' якщо немає):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == PHONE:
        await msg.reply_text(
            "Введіть номер телефону у форматі +380XXXXXXXXX або 0XXXXXXXXXX:",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == DOC_TYPE:
        await msg.reply_text("Оберіть тип документа:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=doc_type_keyboard)
    elif state == PASS_SERIES:
        await msg.reply_text("Введіть серію паспорта (2 літери):", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == PASS_NUMBER:
        await msg.reply_text("Введіть номер паспорта (6 цифр):", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == PASS_ISSUER:
        await msg.reply_text("Введіть, ким виданий паспорт:", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == PASS_DATE:
        await msg.reply_text(
            "Введіть дату видачі паспорта (дд.мм.рррр):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == IDCARD_NUMBER:
        await msg.reply_text("Введіть номер ID-картки (9 цифр):", reply_markup=skip_markup)
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == IDCARD_UNZR:
        await msg.reply_text(
            "Введіть номер запису УНЗР (8 цифр-5 цифр):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == IDCARD_ISSUER:
        await msg.reply_text(
            "Введіть код підрозділу, ким видано ID (4 цифри):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == IDCARD_DATE:
        await msg.reply_text(
            "Введіть дату видачі ID-картки (дд.мм.рррр):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == BIRTH_DATE:
        await msg.reply_text(
            "Введіть дату народження пайовика (дд.мм.рррр):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)
    elif state == BANK_CARD:
        await msg.reply_text(
            "Введіть номер банківської картки (або '-' якщо немає):",
            reply_markup=skip_markup,
        )
        await msg.reply_text("⬇️ Навігація", reply_markup=back_cancel_keyboard)

def is_ipn(text): return re.fullmatch(r"\d{10}", text)
def is_pass_series(text): return re.fullmatch(r"[A-ZА-ЯІЇЄҐ]{2}", text)
def is_pass_number(text): return re.fullmatch(r"\d{6}", text)
def is_unzr(text):
    return re.fullmatch(r"\d{8}-\d{5}", text)

def normalize_unzr(text: str) -> str | None:
    """Validate and format UNZR number."""
    raw = text.strip()
    if re.fullmatch(r"\d{13}", raw):
        return f"{raw[:8]}-{raw[8:]}"
    if re.fullmatch(r"\d{8}-\d{5}", raw):
        return raw
    return None
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

def normalize_bank_card(text):
    digits = re.sub(r"\D", "", text or "")
    if not digits:
        return None
    if len(digits) not in (16, 19):
        return None
    groups = [digits[i:i+4] for i in range(0, len(digits), 4)]
    return " ".join(groups)
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

FIELD_KEYS = {
    IPN: "ipn",
    OBLAST: "oblast",
    RAYON: "rayon",
    SELO: "selo",
    VUL: "vul",
    BUD: "bud",
    KV: "kv",
    PHONE: "phone",
    DOC_TYPE: "doc_type",
    PASS_SERIES: "passport_series",
    PASS_NUMBER: "passport_number",
    PASS_ISSUER: "passport_issuer",
    PASS_DATE: "passport_date",
    IDCARD_NUMBER: "id_number",
    IDCARD_UNZR: "unzr",
    IDCARD_ISSUER: "idcard_issuer",
    IDCARD_DATE: "idcard_date",
    BIRTH_DATE: "birth_date",
    BANK_CARD: "bank_card",
}

NEXT_STATE = {
    IPN: OBLAST,
    OBLAST: RAYON,
    RAYON: SELO,
    SELO: VUL,
    VUL: BUD,
    BUD: KV,
    KV: PHONE,
    PHONE: DOC_TYPE,
    DOC_TYPE: BIRTH_DATE,
    PASS_SERIES: PASS_NUMBER,
    PASS_NUMBER: PASS_ISSUER,
    PASS_ISSUER: PASS_DATE,
    PASS_DATE: BIRTH_DATE,
    IDCARD_NUMBER: IDCARD_UNZR,
    IDCARD_UNZR: IDCARD_ISSUER,
    IDCARD_ISSUER: IDCARD_DATE,
    IDCARD_DATE: BIRTH_DATE,
    BIRTH_DATE: BANK_CARD,
    BANK_CARD: None,
}


async def skip_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    state = int(query.data.split(":")[1])
    key = FIELD_KEYS.get(state)
    if key:
        context.user_data[key] = None
    next_state = NEXT_STATE.get(state)
    if next_state is None:
        return await finalize_payer(update, context)
    await query.message.edit_text("⏭ Пропущено")
    await prompt_step(query.message, next_state)
    return next_state

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
    await prompt_step(update.message, IPN)
    return IPN

async def add_payer_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, FIO)
    if result is not None:
        return result
    if not is_ipn(update.message.text):
        await update.message.reply_text("❗️ ІПН має бути 10 цифр. Спробуйте ще раз:")
        return IPN
    context.user_data["ipn"] = update.message.text
    await prompt_step(update.message, OBLAST)
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
    await prompt_step(update.message, RAYON)
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
    await prompt_step(update.message, SELO)
    return SELO

async def add_payer_selo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, RAYON)
    if result is not None:
        return result
    context.user_data["selo"] = update.message.text
    await prompt_step(update.message, VUL)
    return VUL

async def add_payer_vul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, SELO)
    if result is not None:
        return result
    context.user_data["vul"] = update.message.text
    await prompt_step(update.message, BUD)
    return BUD

async def add_payer_bud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, VUL)
    if result is not None:
        return result
    context.user_data["bud"] = update.message.text
    await prompt_step(update.message, KV)
    return KV

async def add_payer_kv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, BUD)
    if result is not None:
        return result
    context.user_data["kv"] = update.message.text
    await prompt_step(update.message, PHONE)
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
    await prompt_step(update.message, DOC_TYPE)
    return DOC_TYPE

async def add_payer_doc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Паспорт (книжка)":
        context.user_data["doc_type"] = "passport"
        await prompt_step(update.message, PASS_SERIES)
        return PASS_SERIES
    elif text == "ID картка":
        context.user_data["doc_type"] = "id_card"
        await prompt_step(update.message, IDCARD_NUMBER)
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
    await prompt_step(update.message, PASS_NUMBER)
    return PASS_NUMBER

async def add_payer_pass_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_SERIES)
    if result is not None:
        return result
    if not is_pass_number(update.message.text):
        await update.message.reply_text("❗️ Номер паспорта — 6 цифр.")
        return PASS_NUMBER
    context.user_data["passport_number"] = update.message.text
    await prompt_step(update.message, PASS_ISSUER)
    return PASS_ISSUER

async def add_payer_pass_issuer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_NUMBER)
    if result is not None:
        return result
    context.user_data["passport_issuer"] = update.message.text
    await prompt_step(update.message, PASS_DATE)
    return PASS_DATE

async def add_payer_pass_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_ISSUER)
    if result is not None:
        return result
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return PASS_DATE
    context.user_data["passport_date"] = update.message.text
    await prompt_step(update.message, BIRTH_DATE)
    return BIRTH_DATE

async def add_payer_idcard_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, DOC_TYPE)
    if result is not None:
        return result
    if not is_idcard_number(update.message.text):
        await update.message.reply_text("❗️ Номер ID-картки — 9 цифр.")
        return IDCARD_NUMBER
    context.user_data["id_number"] = update.message.text
    await prompt_step(update.message, IDCARD_UNZR)
    return IDCARD_UNZR

async def add_payer_idcard_unzr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, IDCARD_NUMBER)
    if result is not None:
        return result
    unzr = normalize_unzr(update.message.text)
    if not unzr:
        await update.message.reply_text(
            "⚠️ Невірний формат. Має бути 8 цифр, дефіс, 5 цифр."
        )
        return IDCARD_UNZR
    context.user_data["unzr"] = unzr
    await prompt_step(update.message, IDCARD_ISSUER)
    return IDCARD_ISSUER

async def add_payer_idcard_issuer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, IDCARD_UNZR)
    if result is not None:
        return result
    if not is_idcard_issuer(update.message.text):
        await update.message.reply_text("❗️ Код підрозділу — 4 цифри.")
        return IDCARD_ISSUER
    context.user_data["idcard_issuer"] = update.message.text
    await prompt_step(update.message, IDCARD_DATE)
    return IDCARD_DATE

async def add_payer_idcard_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, IDCARD_ISSUER)
    if result is not None:
        return result
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return IDCARD_DATE
    context.user_data["idcard_date"] = update.message.text
    await prompt_step(update.message, BIRTH_DATE)
    return BIRTH_DATE

async def add_payer_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, PASS_DATE if context.user_data.get("doc_type") == "passport" else IDCARD_DATE)
    if result is not None:
        return result
    if not is_date(update.message.text):
        await update.message.reply_text("❗️ Формат дати: дд.мм.рррр")
        return BIRTH_DATE
    context.user_data["birth_date"] = update.message.text
    await prompt_step(update.message, BANK_CARD)
    return BANK_CARD

async def add_payer_bank_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, BIRTH_DATE)
    if result is not None:
        return result
    text = update.message.text.strip()
    if text != "-":
        card = normalize_bank_card(text)
        if not card:
            await update.message.reply_text("❗️ Введіть 16 або 19 цифр картки")
            return BANK_CARD
        context.user_data["bank_card"] = card
    await finalize_payer(update, context)
    return ConversationHandler.END


async def finalize_payer(update: Update | CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Create payer in DB and show post-actions."""
    msg = update.message if update.message else update.callback_query.message
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
        bank_card=d.get("bank_card"),
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

    final_keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Створити договір оренди", callback_data=f"create_contract:{payer_id}")],
            [InlineKeyboardButton("📍 Додати ділянку", callback_data=f"start_land:{payer_id}")],
            [InlineKeyboardButton("До меню", callback_data="to_menu")],
        ]
    )

    context.user_data.clear()
    context.user_data["post_create_msg"] = "✅ Пайовика додано!"
    context.user_data["post_create_markup"] = final_keyboard

    await msg.reply_text(
        "✅ Об’єкт створено.\n📎 Бажаєте одразу додати документи?",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Додати зараз", callback_data=f"add_docs:{'payer_passport' if d.get('doc_type') == 'passport' else 'payer_id'}:{payer_id}")],
                [InlineKeyboardButton("Пропустити", callback_data=f"skip_docs:{'payer_passport' if d.get('doc_type') == 'passport' else 'payer_id'}:{payer_id}")],
            ]
        ),
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
        status = " 🕯" if getattr(p, "is_deceased", False) else ""
        button = InlineKeyboardButton("Картка", callback_data=f"payer_card:{p.id}")
        await update.message.reply_text(
            f"{p.id}. {p.name}{status} (ІПН: {p.ipn})",
            reply_markup=InlineKeyboardMarkup([[button]])
        )

from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler
import sqlalchemy
from db import database, Payer, UploadedDocs, Heir

async def payer_card(update, context):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    select = Payer.select().where(Payer.c.id == payer_id)
    payer = await database.fetch_one(select)
    if not payer:
        await query.answer("Пайовик не знайдений!")
        return ConversationHandler.END

    deceased_note = " <i>🕯 Помер</i>" if payer["is_deceased"] else ""
    text = (
        f"<b>{payer.name}</b>{deceased_note}\n"
        f"🆔 ID: {payer.id}\n"
        f"📇 ІПН: {payer.ipn}\n"
        f"🎂 Дата народження: {payer.birth_date}\n"
        f"📞 Телефон: {payer.phone}\n"
        f"📑 Тип документа: {payer.doc_type}\n"
        f"🛂 Паспорт/ID: {payer.passport_series or ''} {payer.passport_number or ''} {payer.id_number or ''}\n"
        f"Ким виданий: {payer.passport_issuer or payer.idcard_issuer or ''}\n"
        f"Коли виданий: {payer.passport_date or payer.idcard_date or ''}\n"
        f"УНЗР: {payer.unzr or '-'}\n"
        f"🏦 Картка для виплат:\n{payer.bank_card or '-'}\n"
        f"🏠 Адреса: {payer.oblast} обл., {payer.rayon} р-н, с. {payer.selo}, вул. {payer.vul}, буд. {payer.bud}, кв. {payer.kv}"
    )
    if payer["is_deceased"]:
        debt_rows = await database.fetch_all(
            sqlalchemy.select(InheritanceDebt.c.amount)
            .where(InheritanceDebt.c.payer_id == payer_id)
            .where(InheritanceDebt.c.paid == False)
        )
        if debt_rows:
            total_debt = sum(float(r["amount"]) for r in debt_rows)
            text += f"\n⚠️ Є заборгованість перед спадкоємцем: {format_money(total_debt)}"

    heirs = await database.fetch_all(
        Heir.select().where(Heir.c.deceased_payer_id == payer_id)
    )
    if heirs:
        heir_lines = []
        for h in heirs:
            hp = await database.fetch_one(
                Payer.select().where(Payer.c.id == h["heir_payer_id"])
            )
            if hp:
                docs = ", ".join(os.path.basename(d) for d in h["documents"] or [])
                line = f"{hp['name']} (ID: {hp['id']})"
                if docs:
                    line += f" — {docs}"
                heir_lines.append(line)
        if heir_lines:
            text += "\n\n<b>Спадкоємці:</b>\n" + "\n".join(heir_lines)

    if payer["is_deceased"]:
        transfers = await database.fetch_all(
            InheritanceTransfer.select().where(
                InheritanceTransfer.c.deceased_payer_id == payer_id
            )
        )
        land_ids = [t["asset_id"] for t in transfers if t["asset_type"] == "land"]
        contract_ids = [t["asset_id"] for t in transfers if t["asset_type"] == "contract"]
        if land_ids:
            lands = await database.fetch_all(
                sqlalchemy.select(LandPlot.c.cadaster).where(LandPlot.c.id.in_(land_ids))
            )
            text += "\n\n<b>Успадковані ділянки:</b>\n" + "\n".join(
                l["cadaster"] for l in lands
            )
        if contract_ids:
            contracts = await database.fetch_all(
                sqlalchemy.select(Contract.c.number).where(Contract.c.id.in_(contract_ids))
            )
            text += "\n<b>Успадковані договори:</b>\n" + "\n".join(
                c["number"] for c in contracts
            )

    as_heir = await database.fetch_one(
        Heir.select().where(Heir.c.heir_payer_id == payer_id)
    )
    if as_heir:
        deceased = await database.fetch_one(
            Payer.select().where(Payer.c.id == as_heir["deceased_payer_id"])
        )
        if deceased:
            text += (
                f"\n\n<b>Спадкоємець від:</b> {deceased['name']} "
                f"(ID: {deceased['id']})"
            )
        docs = ", ".join(os.path.basename(d) for d in as_heir["documents"] or [])
        if docs:
            text += f"\nДокументи: {docs}"
        transfers = await database.fetch_all(
            InheritanceTransfer.select().where(
                InheritanceTransfer.c.heir_payer_id == payer_id
            )
        )
        land_ids = [t["asset_id"] for t in transfers if t["asset_type"] == "land"]
        contract_ids = [t["asset_id"] for t in transfers if t["asset_type"] == "contract"]
        if land_ids:
            lands = await database.fetch_all(
                sqlalchemy.select(LandPlot.c.cadaster).where(LandPlot.c.id.in_(land_ids))
            )
            text += "\n\n<b>Отримані ділянки:</b>\n" + "\n".join(
                l["cadaster"] for l in lands
            )
        if contract_ids:
            contracts = await database.fetch_all(
                sqlalchemy.select(Contract.c.number).where(Contract.c.id.in_(contract_ids))
            )
            text += "\n<b>Отримані договори:</b>\n" + "\n".join(
                c["number"] for c in contracts
            )
        debt_rows = await database.fetch_all(
            sqlalchemy.select(InheritanceDebt.c.amount, Contract.c.number)
            .join(Contract, Contract.c.id == InheritanceDebt.c.contract_id)
            .where(InheritanceDebt.c.heir_id == payer_id)
            .where(InheritanceDebt.c.paid == False)
        )
        if debt_rows:
            text += "\n\n<b>Борги за договорами:</b>\n" + "\n".join(
                f"№{r['number']} — {format_money(float(r['amount']))}" for r in debt_rows
            )
            total_debt = sum(float(r['amount']) for r in debt_rows)
            text += f"\nВсього борг: {format_money(total_debt)}"

    from crm.events_integration import get_events_text, events_button
    events_block = await get_events_text("payer", payer.id)
    text += "\n\n" + events_block

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
    other_buttons = [
        [InlineKeyboardButton("Редагувати", callback_data=f"edit_payer:{payer.id}")],
        [InlineKeyboardButton("Видалити", callback_data=f"delete_payer:{payer.id}")],
    ]
    if payer["is_deceased"]:
        other_buttons.append(
            [InlineKeyboardButton("Додати спадкоємця", callback_data=f"add_heir:{payer.id}")]
        )
    other_buttons.extend([
        [InlineKeyboardButton("Створити договір оренди", callback_data=f"create_contract:{payer.id}")],
        [events_button("payer", payer.id)],
        [InlineKeyboardButton("До меню", callback_data="to_menu")],
    ])
    keyboard.extend(other_buttons)

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
    payer = await database.fetch_one(
        sqlalchemy.select(Payer.c.is_deceased).where(Payer.c.id == payer_id)
    )
    if payer and payer["is_deceased"]:
        await query.answer()
        await query.message.reply_text(
            "❌ Неможливо додати договір чи виплату. Пайовик позначений як померлий."
        )
        return
    await query.answer()
    await query.message.reply_text(
        f"🔜 Функція створення договору в розробці!\nПайовик #{payer_id}"
    )

async def to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = await get_user_by_tg_id(update.effective_user.id)
    role = user["role"] if user else "user"
    await query.message.reply_text(
        "👋 Вітаємо в ОФІСІ ФЕРМЕРА!\nОберіть розділ:",
        reply_markup=main_menu_admin if role == "admin" else main_menu,
    )
    return ConversationHandler.END

add_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати пайовика$"), add_payer_start)],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_fio), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_ipn), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        OBLAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_oblast), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        RAYON: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_rayon), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        SELO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_selo), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        VUL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_vul), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        BUD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_bud), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        KV: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_kv), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_phone), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        DOC_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_doc_type), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        PASS_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_series), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        PASS_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_number), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        PASS_ISSUER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_issuer), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        PASS_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_pass_date), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        IDCARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_number), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        IDCARD_UNZR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_unzr), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        IDCARD_ISSUER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_issuer), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        IDCARD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_idcard_date), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_birth_date), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
        BANK_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payer_bank_card), CallbackQueryHandler(skip_field, pattern=r"^skip:\d+$")],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
