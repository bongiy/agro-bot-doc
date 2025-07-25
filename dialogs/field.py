from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, InputFile
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from keyboards.menu import fields_menu
from db import database, Field, UploadedDocs
import sqlalchemy
from ftp_utils import download_file_ftp, delete_file_ftp  # <-- додаємо FTP-утиліти

# --- Стани для FSM додавання ---
ASK_FIELD_NAME, ASK_FIELD_AREA = range(2)

# ==== ДОДАВАННЯ ПОЛЯ ====
async def add_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть назву поля:", reply_markup=ReplyKeyboardRemove())
    return ASK_FIELD_NAME

async def add_field_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["field_name"] = update.message.text.strip()
    await update.message.reply_text("Введіть фактичну площу поля, га:")
    return ASK_FIELD_AREA

async def add_field_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        area = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Некоректна площа. Введіть ще раз:")
        return ASK_FIELD_AREA
    name = context.user_data["field_name"]
    query = Field.insert().values(name=name, area_actual=area)
    await database.execute(query)
    await update.message.reply_text(
        f"Поле '{name}' ({area:.4f} га) додано.",
        reply_markup=fields_menu
    )
    context.user_data.clear()
    return ConversationHandler.END

add_field_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати поле$"), add_field_start)],
    states={
        ASK_FIELD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_field_name)],
        ASK_FIELD_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_field_area)],
    },
    fallbacks=[]
)

# ==== СПИСОК ПОЛІВ ====
async def show_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message
    query = sqlalchemy.select(Field)
    fields = await database.fetch_all(query)
    if not fields:
        await msg.reply_text("Поля ще не створені.", reply_markup=fields_menu)
        return
    for f in fields:
        btn = InlineKeyboardButton("Картка", callback_data=f"field_card:{f['id']}")
        await msg.reply_text(
            f"{f['id']}. {f['name']} — {f['area_actual']:.4f} га",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )

# ==== КАРТКА ПОЛЯ ====
async def field_card(update, context):
    query = update.callback_query
    field_id = int(query.data.split(":")[1])
    field = await database.fetch_one(sqlalchemy.select(Field).where(Field.c.id == field_id))
    if not field:
        await query.answer("Поле не знайдено!")
        return
    text = (
        f"<b>Картка поля</b>\n"
        f"ID: {field['id']}\n"
        f"Назва: {field['name']}\n"
        f"Площа фактична: {field['area_actual']:.4f} га"
    )
    kb = []

    # Додати документи до поля
    kb.append([InlineKeyboardButton(
        "📷 Додати документи", callback_data=f"add_docs:field:{field['id']}"
    )])

    # Кнопки перегляду/видалення PDF для поля
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs)
        .where((UploadedDocs.c.entity_type == "field") & (UploadedDocs.c.entity_id == field_id))
    )
    for doc in docs:
        kb.append([
            InlineKeyboardButton(f"⬇️ Завантажити PDF", callback_data=f"send_pdf:{doc['id']}"),
            InlineKeyboardButton(f"🗑 Видалити", callback_data=f"delete_pdf_db:{doc['id']}")
        ])

    # Інші кнопки
    kb.extend([
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit_field:{field['id']}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_field:{field['id']}")],
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_fields_list")]
    ])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# ==== ВИДАЛЕННЯ ПОЛЯ ====
async def delete_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    field_id = int(query.data.split(":")[1])
    from db import LandPlot
    linked = await database.fetch_one(
        sqlalchemy.select(LandPlot).where(LandPlot.c.field_id == field_id)
    )
    if linked:
        await query.answer("Не можна видалити поле — до нього прив'язані ділянки.", show_alert=True)
        return
    await database.execute(Field.delete().where(Field.c.id == field_id))
    await query.answer("Поле видалено!")
    await query.message.edit_text("Поле видалено.")

# ==== ВИДАЛЕННЯ PDF (через FTP) ====
async def delete_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        try:
            delete_file_ftp(row['remote_path'])
        except Exception:
            pass  # ігноруємо, якщо не знайдено на FTP
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
        filename = remote_path.split('/')[-1]
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
async def to_fields_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_fields(update, context)

# ==== РЕДАГУВАННЯ ПОЛЯ (ЗАГЛУШКА — перенеси в edit_field.py) ====
async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    field_id = int(query.data.split(":")[1])
    await query.answer()
    await query.message.reply_text(f"✏️ Функція редагування поля #{field_id} у розробці.")
