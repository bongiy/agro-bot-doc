from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from keyboards.menu import lands_menu
from db import database, LandPlot, Field
import sqlalchemy

async def show_lands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = sqlalchemy.select(LandPlot)
    lands = await database.fetch_all(query)
    if not lands:
        await update.message.reply_text("Ділянки ще не створені.", reply_markup=lands_menu)
        return
    field_ids = {l['field_id'] for l in lands if l['field_id']}
    fields_map = {}
    if field_ids:
        fields = await database.fetch_all(sqlalchemy.select(Field).where(Field.c.id.in_(field_ids)))
        fields_map = {f['id']: f['name'] for f in fields}
    for l in lands:
        fname = fields_map.get(l['field_id'], '—')
        btn = InlineKeyboardButton("Картка", callback_data=f"land_card:{l['id']}")
        await update.message.reply_text(
            f"{l['id']}. {l['cadaster']} — {l['area']:.4f} га, поле: {fname}",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )

async def land_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    land = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == land_id))
    field_name = "—"
    if land and land['field_id']:
        field = await database.fetch_one(sqlalchemy.select(Field).where(Field.c.id == land['field_id']))
        if field:
            field_name = field['name']
    if not land:
        await query.answer("Ділянка не знайдена!")
        return
    text = (
        f"<b>Картка ділянки</b>\n"
        f"ID: {land['id']}\n"
        f"Кадастр: {land['cadaster']}\n"
        f"Площа: {land['area']:.4f} га\n"
        f"НГО: {land['ngo'] if land['ngo'] else '-'}\n"
        f"Поле: {field_name}"
    )
    kb = [
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit_land:{land['id']}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_land:{land['id']}")],
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_lands_list")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def delete_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    await database.execute(LandPlot.delete().where(LandPlot.c.id == land_id))
    await query.answer("Ділянку видалено!")
    await query.message.edit_text("Ділянку видалено.")

# Для повернення зі списку (з callback-кнопки)
async def to_lands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_lands(update, context)
