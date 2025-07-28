from datetime import datetime, date
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
import sqlalchemy

from dialogs.payer import to_menu

from io import BytesIO, StringIO
import csv

from db import (
    database,
    Contract,
    Payment,
    Payer,
    ContractLandPlot,
    LandPlot,
)
from contract_generation_v2 import format_money

PAY_AMOUNT, PAY_DATE, PAY_TYPE, PAY_NOTES, PAY_CONFIRM = range(5)

payment_type_map = {
    "cash": "\ud83d\udcb8 Готівка",
    "card": "\ud83d\udcb3 Картка",
    "bank": "\ud83c\udfe6 Рахунок",
}


def short_fio(full_name: str) -> str:
    parts = full_name.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return full_name


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


# ==== ГЛОБАЛЬНИЙ ПОШУК ПАЙОВИКА ====
SEARCH_PAYER = 2001


async def global_add_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть частину ПІБ пайовика:")
    return SEARCH_PAYER


async def global_add_payment_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    term = update.message.text.strip()
    rows = await database.fetch_all(
        sqlalchemy.select(Payer.c.id, Payer.c.name)
        .where(Payer.c.name.ilike(f"%{term}%"))
        .limit(10)
    )
    if not rows:
        await update.message.reply_text("Нічого не знайдено. Спробуйте ще:")
        return SEARCH_PAYER
    keyboard = [
        [InlineKeyboardButton(f"\U0001F464 {r['name']}", callback_data=f"pay_select:{r['id']}")]
        for r in rows
    ]
    keyboard.append([InlineKeyboardButton("❌ Скасувати", callback_data="to_menu")])
    await update.message.reply_text(
        "Оберіть пайовика:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def select_payer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    contracts = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.number,
            sqlalchemy.func.sum(LandPlot.c.area).label("area"),
        )
        .select_from(Contract)
        .join(ContractLandPlot, Contract.c.id == ContractLandPlot.c.contract_id)
        .join(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .where(Contract.c.payer_id == payer_id)
        .group_by(Contract.c.id)
    )
    if not contracts:
        await query.answer("Договори не знайдено!", show_alert=True)
        return
    if len(contracts) == 1:
        cid = contracts[0]["id"]
        orig = query.data
        query.data = f"add_payment:{cid}"
        result = await add_payment_start(update, context)
        query.data = orig
        return result
    keyboard = [
        [
            InlineKeyboardButton(
                f"\U0001F4C4 №{c['number']} ({c['area']:.4f} га)",
                callback_data=f"pay_contract:{c['id']}",
            )
        ]
        for c in contracts
    ]
    await query.message.edit_text("Оберіть договір:", reply_markup=InlineKeyboardMarkup(keyboard))


async def select_contract_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cid = int(query.data.split(":")[1])
    orig = query.data
    query.data = f"add_payment:{cid}"
    result = await add_payment_start(update, context)
    query.data = orig
    return result


# ==== СПИСОК ОСТАННІХ ВИПЛАТ ====
async def show_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message
    rows = await database.fetch_all(
        sqlalchemy.select(
            Payment.c.agreement_id,
            Payment.c.payment_date,
            Payment.c.amount,
            Contract.c.number,
            Payer.c.name,
        )
        .select_from(Payment)
        .join(Contract, Contract.c.id == Payment.c.agreement_id)
        .join(Payer, Payer.c.id == Contract.c.payer_id)
        .order_by(Payment.c.payment_date.desc())
        .limit(10)
    )
    if not rows:
        await msg.reply_text("Виплати відсутні.")
        return
    for r in rows:
        text = (
            f"\U0001F4C5 {r['payment_date'].strftime('%d.%m.%Y')} — {format_money(r['amount'])}\n"
            f"\U0001F464 {short_fio(r['name'])} — \U0001F4C4 №{r['number']}"
        )
        btn = InlineKeyboardButton(
            "\U0001F4DC Детальніше",
            callback_data=f"agreement_card:{r['agreement_id']}",
        )
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup([[btn]]))


# ==== ЗВІТИ ПО ВИПЛАТАХ ====
async def payment_reports_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = datetime.utcnow().year
    years = [str(year - i) for i in range(3)]
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(y, callback_data=f"pay_report:{y}") for y in years]]
    )
    await update.message.reply_text("\U0001F4C6 Оберіть рік:", reply_markup=kb)


async def payment_report_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    year = int(query.data.split(":")[1])
    rows = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.number,
            Contract.c.rent_amount,
            Payer.c.name,
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.c.amount), 0).label("paid"),
        )
        .select_from(Contract)
        .join(Payer, Payer.c.id == Contract.c.payer_id)
        .outerjoin(
            Payment,
            (Payment.c.agreement_id == Contract.c.id)
            & (sqlalchemy.extract('year', Payment.c.payment_date) == year),
        )
        .group_by(Contract.c.id, Payer.c.name)
        .order_by(Payer.c.name)
    )
    total = 0.0
    lines = [f"\U0001F4CA Звіт по виплатах за {year} рік:", ""]
    for r in rows:
        paid = float(r["paid"] or 0)
        total += paid
        rent = float(r["rent_amount"] or 0)
        fio = short_fio(r["name"])
        if paid >= rent:
            lines.append(f"\U0001F464 {fio} — \U0001F4C4 №{r['number']} — ✅ {format_money(paid)}")
        else:
            debt = format_money(rent - paid)
            lines.append(
                f"\U0001F464 {fio} — \U0001F4C4 №{r['number']} — ❌ {format_money(paid)} (борг {debt})"
            )
    lines.append("")
    lines.append(f"\U0001F4B0 Всього виплачено: {format_money(total)}")
    lines.append(f"\U0001F4CC Договорів: {len(rows)}")
    kb = [
        [InlineKeyboardButton("\U0001F4E4 Завантажити звіт", callback_data=f"pay_csv:{year}")],
        [InlineKeyboardButton("\U0001F501 Назад", callback_data="payment_reports")],
    ]
    await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))


async def payment_report_csv_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    year = int(query.data.split(":")[1])
    rows = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.number,
            Payer.c.name,
            Contract.c.rent_amount,
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.c.amount), 0).label("paid"),
        )
        .select_from(Contract)
        .join(Payer, Payer.c.id == Contract.c.payer_id)
        .outerjoin(
            Payment,
            (Payment.c.agreement_id == Contract.c.id)
            & (sqlalchemy.extract('year', Payment.c.payment_date) == year),
        )
        .group_by(Contract.c.id, Payer.c.name)
        .order_by(Payer.c.name)
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Payer", "Contract", "Rent", "Paid", "Debt"])
    for r in rows:
        rent = float(r["rent_amount"] or 0)
        paid = float(r["paid"] or 0)
        writer.writerow([r["name"], r["number"], rent, paid, rent - paid])
    output.seek(0)
    bio = BytesIO(output.getvalue().encode("utf-8"))
    await query.message.reply_document(
        document=InputFile(bio, filename=f"payments_{year}.csv")
    )


global_add_payment_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати виплату$"), global_add_payment_start)],
    states={
        SEARCH_PAYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, global_add_payment_search)],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
