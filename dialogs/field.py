from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from keyboards.menu import fields_menu
from db import database, Field, UploadedDocs
import sqlalchemy

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
import sqlalchemy
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db import database, Field, UploadedDocs

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

    # Додати документи до поля (можна додати за потреби)
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
            InlineKeyboardButton(f"📄 {doc['doc_type']}", url=doc['web_link']),
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
async def delete_pdf_db(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    from db import UploadedDocs
    import sqlalchemy
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        from drive_utils import delete_pdf_from_drive
        delete_pdf_from_drive(row['gdrive_file_id'])
        await database.execute(UploadedDocs.delete().where(UploadedDocs.c.id == doc_id))
        await query.answer("Документ видалено!")
        await query.message.edit_text("Документ видалено. Оновіть картку для перегляду змін.")
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
