from telegram import Update, ReplyKeyboardRemove
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
    query = sqlalchemy.select(Field)
    fields = await database.fetch_all(query)
    if not fields:
        await update.message.reply_text("Поля ще не створені.", reply_markup=fields_menu)
        return
    text = "\n".join([f"{f['id']}. {f['name']} — {f['area_actual']:.4f} га" for f in fields])
    await update.message.reply_text(f"Список полів:\n{text}", reply_markup=fields_menu)
