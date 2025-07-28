from datetime import datetime, date
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import sqlalchemy

from db import database, Contract, Payment
from contract_generation_v2 import format_money

PAY_AMOUNT, PAY_DATE, PAY_TYPE, PAY_NOTES, PAY_CONFIRM = range(5)

payment_type_map = {
    "cash": "\ud83d\udcb8 Готівка",
    "card": "\ud83d\udcb3 Картка",
    "bank": "\ud83c\udfe6 Рахунок",
}


async def add_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(
        sqlalchemy.select(Contract).where(Contract.c.id == contract_id)
    )
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return ConversationHandler.END
    context.user_data["payment_contract_id"] = contract_id
    rent = float(contract["rent_amount"] or 0)
    context.user_data["payment_default_amount"] = rent
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("\ud83d\udcb0 Повна сума", callback_data="full_amount")],
        [InlineKeyboardButton("\u274c Скасувати", callback_data=f"agreement_card:{contract_id}")],
    ])
    await query.message.edit_text(
        f"Введіть суму виплати (за замовчуванням {format_money(rent)}):",
        reply_markup=keyboard,
    )
    return PAY_AMOUNT


async def payment_set_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        amount = context.user_data.get("payment_default_amount", 0)
    else:
        text = update.message.text.replace(",", ".").strip()
        try:
            amount = float(text)
        except ValueError:
            await update.message.reply_text("Введіть коректну суму:")
            return PAY_AMOUNT
    context.user_data["payment_amount"] = amount
    await (update.callback_query.message if update.callback_query else update.message).reply_text(
        "Введіть дату виплати (ДД.ММ.РРРР) або '-' для сьогодні:")
    return PAY_DATE


async def payment_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        pay_date = date.today()
    else:
        try:
            pay_date = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await update.message.reply_text("Формат дати ДД.ММ.РРРР або '-':")
            return PAY_DATE
    context.user_data["payment_date"] = pay_date
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("\ud83d\udcb8 Готівка", callback_data="ptype:cash")],
        [InlineKeyboardButton("\ud83d\udcb3 Картка", callback_data="ptype:card")],
        [InlineKeyboardButton("\ud83c\udfe6 Рахунок", callback_data="ptype:bank")],
    ])
    await update.message.reply_text("Оберіть тип виплати:", reply_markup=kb)
    return PAY_TYPE


async def payment_set_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ptype = query.data.split(":")[1]
    context.user_data["payment_type"] = ptype
    await query.message.edit_text("Введіть коментар або '-' щоб пропустити:")
    return PAY_NOTES


async def payment_set_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        text = ""
    context.user_data["payment_notes"] = text
    cid = context.user_data["payment_contract_id"]
    amount = format_money(context.user_data["payment_amount"])
    pdate = context.user_data["payment_date"].strftime("%d.%m.%Y")
    ptype = payment_type_map.get(context.user_data["payment_type"], "")
    notes = text or "-"
    msg = (
        f"Сума: {amount}\n"
        f"Дата: {pdate}\n"
        f"Тип: {ptype}\n"
        f"Коментар: {notes}\n\n"
        "Підтвердити збереження?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("\u2705 Зберегти", callback_data="payment_save")],
        [InlineKeyboardButton("\u274c Скасувати", callback_data=f"agreement_card:{cid}")],
    ])
    await update.message.reply_text(msg, reply_markup=kb)
    return PAY_CONFIRM


async def payment_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = context.user_data.get("payment_contract_id")
    await database.execute(
        Payment.insert().values(
            agreement_id=cid,
            amount=context.user_data.get("payment_amount"),
            payment_date=context.user_data.get("payment_date"),
            payment_type=context.user_data.get("payment_type"),
            notes=context.user_data.get("payment_notes"),
            created_at=datetime.utcnow(),
        )
    )
    context.user_data.clear()
    await query.message.edit_text(
        "✅ Виплату збережено",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{cid}")]]),
    )
    return ConversationHandler.END


add_payment_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_payment_start, pattern=r"^add_payment:\d+$")],
    states={
        PAY_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_amount),
            CallbackQueryHandler(payment_set_amount, pattern=r"^full_amount$")
        ],
        PAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_date)],
        PAY_TYPE: [CallbackQueryHandler(payment_set_type, pattern=r"^ptype:\w+$")],
        PAY_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_notes)],
        PAY_CONFIRM: [CallbackQueryHandler(payment_save, pattern=r"^payment_save$")],
    },
    fallbacks=[],
)
