from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from keyboards.menu import lands_menu
from db import database, LandPlot, Field
import sqlalchemy

ASK_CADASTER, ASK_AREA, ASK_NGO, ASK_FIELD = range(4)

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
    query = LandPlot.insert().values(
        cadaster=context.user_data["cadaster"],
        area=context.user_data["area"],
        ngo=context.user_data["ngo"],
        field_id=field_id
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
    },
    fallbacks=[]
)


async def show_lands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import sqlalchemy
    from db import Field
    query = sqlalchemy.select(LandPlot)
    lands = await database.fetch_all(query)
    if not lands:
        await update.message.reply_text("Ділянки ще не створені.", reply_markup=lands_menu)
        return

    # Отримаємо всі поля разом, щоб не робити запит для кожної ділянки
    field_ids = {l['field_id'] for l in lands if l['field_id']}
    fields_map = {}
    if field_ids:
        fields = await database.fetch_all(sqlalchemy.select(Field).where(Field.c.id.in_(field_ids)))
        fields_map = {f['id']: f['name'] for f in fields}

    for l in lands:
        fname = fields_map.get(l['field_id'], '—')
        buttons = [
            [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_land:{l['id']}")]
        ]
        await update.message.reply_text(
            f"{l['id']}. {l['cadaster']} — {l['area']:.4f} га, поле: {fname}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
async def delete_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    await database.execute(LandPlot.delete().where(LandPlot.c.id == land_id))
    await query.answer("Ділянку видалено!")
    await query.message.edit_text("Ділянку видалено.")
