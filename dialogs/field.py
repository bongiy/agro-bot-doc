from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from keyboards.menu import fields_menu
from db import database, Field
import sqlalchemy

ASK_FIELD_NAME, ASK_FIELD_AREA = range(2)

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



async def show_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import sqlalchemy
    query = sqlalchemy.select(Field)
    fields = await database.fetch_all(query)
    if not fields:
        await update.message.reply_text("Поля ще не створені.", reply_markup=fields_menu)
        return
    for f in fields:
        buttons = [
            [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_field:{f['id']}")]
        ]
        await update.message.reply_text(
            f"{f['id']}. {f['name']} — {f['area_actual']:.4f} га",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

async def delete_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    field_id = int(query.data.split(":")[1])
    # Перевіряємо, чи є ділянки з цим полем
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
