from telegram import Update, InputFile
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

from handlers.menu import admin_only
from dialogs.payer import to_menu
from db import (
    get_company_report,
    get_company_contract_types,
    get_company_sublease,
    get_company_payments_by_year,
)
from keyboards.reports import report_nav_kb
from utils.company_report import company_report_to_excel
from contract_generation_v2 import format_money

CR_YEAR, CR_SHOW = range(2)


@admin_only
async def company_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть рік:")
    return CR_YEAR


@admin_only
async def company_report_set_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        year = int(text)
    except ValueError:
        await update.message.reply_text("Введіть рік числом:")
        return CR_YEAR
    context.user_data["cr_year"] = year
    await update.message.reply_text("Формую звіт...")
    summary = await get_company_report(year)
    types = await get_company_contract_types(year)
    sublease = await get_company_sublease()
    payments = await get_company_payments_by_year()
    context.user_data["cr_summary"] = summary
    context.user_data["cr_types"] = types
    context.user_data["cr_sublease"] = sublease
    context.user_data["cr_payments"] = payments

    lines: list[str] = []
    for s in summary:
        rent = float(s["rent_total"] or 0)
        paid = float(s["paid_total"] or 0)
        coverage = paid / rent * 100 if rent else 0
        lines.append(
            (
                f"🏢 {s['name']}\n"
                f"📄 Договорів: {s['contracts']} | 📍 Ділянок: {s['plots']}\n"
                f"📐 В обробітку: {float(s['physical_area'] or 0):.2f} га | "
                f"📏 По договорах: {float(s['contract_area'] or 0):.2f} га\n"
                f"👤 Пайовиків: {s['payers']}\n"
                f"💰 Оренда ({year}): {format_money(rent)} | "
                f"💸 Виплачено: {format_money(paid)}\n"
                f"✅ Покрито: {coverage:.2f}%"
            )
        )
    text = "\n\n".join(lines) if lines else "Немає даних."
    kb = report_nav_kb(False, False)
    await update.message.reply_text(text, reply_markup=kb)
    return CR_SHOW


@admin_only
async def company_report_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    summary = context.user_data.get("cr_summary", [])
    types = context.user_data.get("cr_types", [])
    sublease = context.user_data.get("cr_sublease", [])
    payments = context.user_data.get("cr_payments", [])
    bio = company_report_to_excel(summary, types, sublease, payments)
    await query.message.reply_document(
        document=InputFile(bio, filename="company_report.xlsx")
    )
    await query.answer()
    return CR_SHOW


company_report_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^🏢 Звіт по ТОВ$"), company_report_start)
    ],
    states={
        CR_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, company_report_set_year)],
        CR_SHOW: [CallbackQueryHandler(company_report_export, pattern=r"^payrep_export$")],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
