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
from db import get_contract_overview
from keyboards.reports import report_nav_kb
from utils.reports import contracts_overview_to_excel, CONTRACT_STATUS_LABELS
from contract_generation_v2 import format_money

(CO_SHOW,) = range(1)


@admin_only
async def contract_overview_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Формую звіт...")
    summary, companies, statuses, years, _ = await get_contract_overview()
    lines: list[str] = [
        "📑 <b>Узагальнений звіт по договорах</b>",
        f"📄 Договорів: {summary['contracts']}",
        f"👤 Пайовиків: {summary['payers']}",
        f"📏 Площа: {summary['area']:.2f} га",
        f"💰 Річна плата: {format_money(summary['rent'])}",
        f"🏢 ТОВ: {summary['companies']}",
    ]
    if companies:
        lines.append("\n🏢 <b>По компаніях:</b>")
        for c in companies:
            lines.append(
                f"• {c['name']}: {c['contracts']} договорів / {float(c['area'] or 0):.2f} га / {format_money(c['rent'])}"
            )
    if statuses:
        lines.append("\n📍 <b>По статусах:</b>")
        for s in statuses:
            label = CONTRACT_STATUS_LABELS.get(s['status'], s['status'])
            lines.append(f"• {label} — {s['contracts']}")
    if years:
        lines.append("\n📅 <b>За роком завершення:</b>")
        for y in years:
            lines.append(f"• {int(y['year']) if y['year'] is not None else '—'}: {y['contracts']} договорів")
    await msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=report_nav_kb(False, False))
    return CO_SHOW


@admin_only
async def contract_overview_export_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    summary, companies, statuses, years, rows = await get_contract_overview()
    bio = await contracts_overview_to_excel(rows, companies, statuses, years, summary)
    await query.message.reply_document(document=InputFile(bio, filename="contracts_overview.xlsx"))
    await query.answer()
    return CO_SHOW


contract_overview_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^📑 Узагальнений звіт по договорах$"), contract_overview_start)
    ],
    states={
        CO_SHOW: [CallbackQueryHandler(contract_overview_export_cb, pattern=r"^payrep_export$")],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
