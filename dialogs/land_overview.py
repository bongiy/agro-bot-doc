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
from db import get_land_overview
from keyboards.reports import report_nav_kb
from utils.reports import land_overview_to_excel
from contract_generation_v2 import format_money

(
    LO_SHOW,
) = range(1)


@admin_only
async def land_overview_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Формую звіт...")
    summary, fields, companies, statuses, contracts = await get_land_overview()

    lines: list[str] = [
        "📊 <b>Узагальнений звіт по ділянках</b>",
        f"🔢 Ділянок: {summary['plots']}",
        f"📏 Площа: {summary['area']:.2f} га",
        f"💰 НГО: {format_money(summary['ngo'])}",
        f"👤 Пайовиків: {summary['payers']}",
        f"📄 Договорів: {summary['contracts']}",
        f"🏢 ТОВ: {summary['companies']}",
    ]

    if fields:
        lines.append("\n🌾 <b>По полях:</b>")
        for f in fields:
            lines.append(
                f"• {f['name'] or '—'}: {f['plots']} ділянок, {float(f['area'] or 0):.2f} га"
            )

    if contracts:
        lines.append("\n🧾 <b>По договорах:</b>")
        for c in contracts:
            lines.append(
                f"• {c['number']}: {c['plots']} ділянок, {float(c['area'] or 0):.2f} га"
            )

    if statuses:
        lines.append("\n📍 <b>По статусах:</b>")
        for s in statuses:
            status_name = "З договором" if s["status"] == "with_contract" else "Без договору"
            lines.append(
                f"• {status_name} — {s['plots']} ділянок ({float(s['area'] or 0):.2f} га)"
            )

    await msg.edit_text("\n".join(lines), reply_markup=report_nav_kb(False, False), parse_mode="HTML")
    return LO_SHOW


@admin_only
async def land_overview_export_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    summary, fields, companies, statuses, _ = await get_land_overview()
    bio = await land_overview_to_excel(summary, fields, companies, statuses)
    await query.message.reply_document(
        document=InputFile(bio, filename="land_overview.xlsx")
    )
    await query.answer()
    return LO_SHOW


land_overview_conv = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex("^📋 Узагальнений звіт по ділянках$"), land_overview_start
        )
    ],
    states={
        LO_SHOW: [CallbackQueryHandler(land_overview_export_cb, pattern=r"^payrep_export$")],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
