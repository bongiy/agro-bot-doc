from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from keyboards.menu import fields_menu
from db import database, Field
import sqlalchemy

async def show_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = sqlalchemy.select(Field)
    fields = await database.fetch_all(query)
    if not fields:
        await update.message.reply_text("Поля ще не створені.", reply_markup=fields_menu)
        return
    for f in fields:
        btn = InlineKeyboardButton("Картка", callback_data=f"field_card:{f['id']}")
        await update.message.reply_text(
            f"{f['id']}. {f['name']} — {f['area_actual']:.4f} га",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )

async def field_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    kb = [
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit_field:{field['id']}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_field:{field['id']}")],
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_fields_list")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

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

# Для повернення зі списку (з callback-кнопки)
async def to_fields_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_fields(update, context)
