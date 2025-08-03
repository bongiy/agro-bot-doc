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
from db import get_fields_report
from keyboards.reports import report_nav_kb
from utils.reports import fields_report_to_excel


(FR_SHOW,) = range(1)


@admin_only
async def fields_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Формую звіт...")
    rows = await get_fields_report()

    lines: list[str] = ["📈 <b>Статистика по полях</b>"]
    for r in rows:
        lines.extend(
            [
                f"\n🌾 Поле: {r['name']}",
                f"📐 Фізична площа: {float(r['physical_area'] or 0):.2f} га",
                f"📍 Ділянки: {float(r['plots_area'] or 0):.2f} га",
                f"📄 З договорами: {float(r['contract_area'] or 0):.2f} га",
                f"🔁 Без договорів: {float(r['without_contract'] or 0):.2f} га",
                f"✅ Покриття: {float(r['coverage'] or 0):.2f}%",
            ]
        )

    await msg.edit_text(
        "\n".join(lines),
        reply_markup=report_nav_kb(False, False),
        parse_mode="HTML",
    )
    return FR_SHOW


@admin_only
async def fields_report_export_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    rows = await get_fields_report()
    bio = await fields_report_to_excel(rows)
    await query.message.reply_document(
        document=InputFile(bio, filename="fields_report.xlsx")
    )
    await query.answer()
    return FR_SHOW


fields_report_conv = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex("^📈 Статистика по полях$"), fields_report_start
        )
    ],
    states={
        FR_SHOW: [CallbackQueryHandler(fields_report_export_cb, pattern=r"^payrep_export$")]
    },
    fallbacks=[CommandHandler("start", to_menu)],
)

