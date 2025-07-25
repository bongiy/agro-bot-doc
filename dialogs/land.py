import os
import unicodedata
import re
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from keyboards.menu import lands_menu
from db import database, LandPlot, Field, Payer, UploadedDocs
import sqlalchemy
from ftp_utils import download_file_ftp, delete_file_ftp

# --- Стани для FSM додавання ділянки ---
ASK_CADASTER, ASK_AREA, ASK_NGO, ASK_FIELD, ASK_PAYER = range(5)

def to_latin_filename(text, default="document.pdf"):
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = name.replace(" ", "_")
    name = re.sub(r'[^A-Za-z0-9_.-]', '', name)
    if not name or name.startswith(".pdf") or name.lower() == ".pdf":
        return default
    if not name.lower().endswith('.pdf'):
        name += ".pdf"
    return name

# ==== ДОДАВАННЯ ДІЛЯНКИ ====
async def add_land_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть кадастровий номер ділянки (19 цифр):", reply_markup=ReplyKeyboardRemove())
    return ASK_CADASTER

async def land_cadaster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cad = update.message.text.strip()
    if len(cad.replace(":", "")) != 19:
        await update.message.reply_text("Кадастровий номер має містити 19 цифр. Спробуйте ще раз:")
        return ASK_CADASTER
    context.user_data["cadaster"] = cad
    await update.message.reply_text("Введіть площу ділянки, га:")
    return ASK_AREA

async def land_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        area = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Некоректна площа. Введіть ще раз:")
        return ASK_AREA
    context.user_data["area"] = area
    await update.message.reply_text("Введіть НГО (можна пропустити):")
    return ASK_NGO

async def land_ngo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ngo = float(update.message.text.replace(",", "."))
    except ValueError:
        ngo = None
    context.user_data["ngo"] = ngo
    # Показати вибір поля
    query = sqlalchemy.select(Field)
    fields = await database.fetch_all(query)
    if not fields:
        await update.message.reply_text("Спочатку створіть хоча б одне поле командою ➕ Додати поле!", reply_markup=lands_menu)
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup(
        [[f"{f['id']}: {f['name']}"] for f in fields], resize_keyboard=True
    )
    context.user_data["fields"] = {f"{f['id']}: {f['name']}": f["id"] for f in fields}
    await update.message.reply_text("Оберіть поле для ділянки:", reply_markup=kb)
    return ASK_FIELD

async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_id = context.user_data["fields"].get(update.message.text)
    if not field_id:
        await update.message.reply_text("Оберіть поле зі списку (натисніть кнопку):")
        return ASK_FIELD

    # Далі — запитати, чи додавати власника одразу, чи згодом
    kb = ReplyKeyboardMarkup(
        [["🔍 Обрати власника зараз"], ["Пропустити — додати власника пізніше"]],
        resize_keyboard=True
    )
    context.user_data["field_id"] = field_id
    await update.message.reply_text(
        "Бажаєте одразу обрати власника (пайовика) для ділянки?\n"
        "Можна додати власника згодом у картці ділянки.",
        reply_markup=kb
    )
    return ASK_PAYER

async def choose_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Пропустити — додати власника пізніше":
        query = LandPlot.insert().values(
            cadaster=context.user_data["cadaster"],
            area=context.user_data["area"],
            ngo=context.user_data["ngo"],
            field_id=context.user_data["field_id"],
            payer_id=None
        )
        await database.execute(query)
        await update.message.reply_text("Ділянка додана без власника! Власника можна додати в картці ділянки.", reply_markup=lands_menu)
        context.user_data.clear()
        return ConversationHandler.END

    payers = await database.fetch_all(sqlalchemy.select(Payer).limit(20))
    if not payers:
        await update.message.reply_text("Спочатку додайте хоча б одного пайовика!", reply_markup=lands_menu)
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup(
        [[f"{p['id']}: {p['name']}"] for p in payers],
        resize_keyboard=True
    )
    context.user_data["payers"] = {f"{p['id']}: {p['name']}": p["id"] for p in payers}
    await update.message.reply_text("Оберіть власника (пайовика) для ділянки:", reply_markup=kb)
    return ASK_PAYER + 1

async def set_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payer_id = context.user_data["payers"].get(update.message.text)
    if not payer_id:
        await update.message.reply_text("Оберіть пайовика зі списку (натисніть кнопку):")
        return ASK_PAYER + 1
    query = LandPlot.insert().values(
        cadaster=context.user_data["cadaster"],
        area=context.user_data["area"],
        ngo=context.user_data["ngo"],
        field_id=context.user_data["field_id"],
        payer_id=payer_id
    )
    await database.execute(query)
    await update.message.reply_text("Ділянка додана!", reply_markup=lands_menu)
    context.user_data.clear()
    return ConversationHandler.END

add_land_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати ділянку$"), add_land_start)],
    states={
        ASK_CADASTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_cadaster)],
        ASK_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_area)],
        ASK_NGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_ngo)],
        ASK_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_field)],
        ASK_PAYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_payer)],
        ASK_PAYER + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_payer)],
    },
    fallbacks=[]
)

# ==== СПИСОК ДІЛЯНОК ====
async def show_lands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message
    query = sqlalchemy.select(LandPlot)
    lands = await database.fetch_all(query)
    if not lands:
        await msg.reply_text("Ділянки ще не створені.", reply_markup=lands_menu)
        return
    field_ids = {l['field_id'] for l in lands if l['field_id']}
    fields_map = {}
    if field_ids:
        fields = await database.fetch_all(sqlalchemy.select(Field).where(Field.c.id.in_(field_ids)))
        fields_map = {f['id']: f['name'] for f in fields}
    for l in lands:
        fname = fields_map.get(l['field_id'], '—')
        btn = InlineKeyboardButton("Картка", callback_data=f"land_card:{l['id']}")
        await msg.reply_text(
            f"{l['id']}. {l['cadaster']} — {l['area']:.4f} га, поле: {fname}",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )

# --- Картка ділянки ---
async def land_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    land = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == land_id))
    field_name = "—"
    payer_name = "—"
    if land and land['field_id']:
        field = await database.fetch_one(sqlalchemy.select(Field).where(Field.c.id == land['field_id']))
        if field:
            field_name = field['name']
    if land and land['payer_id']:
        payer = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == land['payer_id']))
        if payer:
            payer_name = payer['name']
    if not land:
        await query.answer("Ділянка не знайдена!")
        return

    text = (
        f"<b>Картка ділянки</b>\n"
        f"ID: {land['id']}\n"
        f"Кадастр: {land['cadaster']}\n"
        f"Площа: {land['area']:.4f} га\n"
        f"НГО: {land['ngo'] if land['ngo'] else '-'}\n"
        f"Поле: {field_name}\n"
        f"Власник: {payer_name}"
    )

    buttons = []
    # --- Додати документи ---
    buttons.append([
        InlineKeyboardButton(
            "📷 Додати документи", callback_data=f"add_docs:land:{land['id']}"
        )
    ])
    # --- Кнопки перегляду/видалення PDF ---
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs)
        .where((UploadedDocs.c.entity_type == "land") & (UploadedDocs.c.entity_id == land_id))
    )
    for doc in docs:
        doc_type = doc['doc_type']
        buttons.append([
            InlineKeyboardButton(f"⬇️ {doc_type}", callback_data=f"send_pdf:{doc['id']}"),
            InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_pdf_db:{doc['id']}")
        ])
    # --- Кнопки власника, інші кнопки ---
    if land['payer_id']:
        buttons.append([InlineKeyboardButton("✏️ Змінити власника", callback_data=f"edit_land_owner:{land['id']}")])
    else:
        buttons.append([InlineKeyboardButton("➕ Додати власника", callback_data=f"edit_land_owner:{land['id']}")])
    buttons.extend([
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit_land:{land['id']}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_land:{land['id']}")],
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_lands_list")]
    ])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ==== ВИДАЛЕННЯ ДІЛЯНКИ ====
async def delete_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    await database.execute(LandPlot.delete().where(LandPlot.c.id == land_id))
    await query.answer("Ділянку видалено!")
    await query.message.edit_text("Ділянку видалено.")

# ==== ВИДАЛЕННЯ PDF через FTP ====
async def delete_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        try:
            delete_file_ftp(row['remote_path'])
        except Exception:
            pass
        await database.execute(UploadedDocs.delete().where(UploadedDocs.c.id == doc_id))
        await query.answer("Документ видалено!")
        await query.message.edit_text("Документ видалено. Оновіть картку для перегляду змін.")
    else:
        await query.answer("Документ не знайдено!", show_alert=True)

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

# ==== ПОВЕРНЕННЯ ДО СПИСКУ ====
async def to_lands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_lands(update, context)
