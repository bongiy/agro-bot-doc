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
from db import get_land_report_rows
from keyboards.reports import report_nav_kb
from utils.reports import land_report_to_excel
from contract_generation_v2 import format_money
from datetime import datetime

(
    LR_PAYER,
    LR_COMPANY,
    LR_CONTRACT,
    LR_CADASTER,
    LR_FIELD,
    LR_AREA_FROM,
    LR_AREA_TO,
    LR_NGO_FROM,
    LR_NGO_TO,
    LR_END_DATE,
    LR_SHOW,
) = range(11)

PAGE_SIZE = 10


@admin_only
async def land_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ПІБ пайовика або '-' для всіх:")
    return LR_PAYER


@admin_only
async def land_set_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["lr_payer"] = None if text == "-" else text
    await update.message.reply_text("Введіть назву компанії-орендаря або '-' для всіх:")
    return LR_COMPANY


@admin_only
async def land_set_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["lr_company"] = None if text == "-" else text
    await update.message.reply_text("Введіть номер договору або '-' для всіх:")
    return LR_CONTRACT


@admin_only
async def land_set_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["lr_contract"] = None if text == "-" else text
    await update.message.reply_text("Введіть кадастровий номер або '-' для всіх:")
    return LR_CADASTER


@admin_only
async def land_set_cadaster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["lr_cadaster"] = None if text == "-" else text
    await update.message.reply_text("Введіть назву поля або '-' для всіх:")
    return LR_FIELD


@admin_only
async def land_set_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["lr_field"] = None if text == "-" else text
    await update.message.reply_text("Площа від (га) або '-' для пропуску:")
    return LR_AREA_FROM


@admin_only
async def land_set_area_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        context.user_data["lr_area_from"] = None
    else:
        try:
            context.user_data["lr_area_from"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Некоректне число. Введіть площу або '-' для пропуску:")
            return LR_AREA_FROM
    await update.message.reply_text("Площа до (га) або '-' для пропуску:")
    return LR_AREA_TO


@admin_only
async def land_set_area_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        context.user_data["lr_area_to"] = None
    else:
        try:
            context.user_data["lr_area_to"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Некоректне число. Введіть площу або '-' для пропуску:")
            return LR_AREA_TO
    await update.message.reply_text("НГО від або '-' для пропуску:")
    return LR_NGO_FROM


@admin_only
async def land_set_ngo_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        context.user_data["lr_ngo_from"] = None
    else:
        try:
            context.user_data["lr_ngo_from"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Некоректне число. Введіть НГО або '-' для пропуску:")
            return LR_NGO_FROM
    await update.message.reply_text("НГО до або '-' для пропуску:")
    return LR_NGO_TO


@admin_only
async def land_set_ngo_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        context.user_data["lr_ngo_to"] = None
    else:
        try:
            context.user_data["lr_ngo_to"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Некоректне число. Введіть НГО або '-' для пропуску:")
            return LR_NGO_TO
    await update.message.reply_text("Дата закінчення договору (ДД.ММ.РРРР) або '-' для пропуску:")
    return LR_END_DATE


@admin_only
async def land_set_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        context.user_data["lr_end_date"] = None
    else:
        try:
            context.user_data["lr_end_date"] = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await update.message.reply_text("Некоректна дата. Введіть у форматі ДД.ММ.РРРР або '-' для пропуску:")
            return LR_END_DATE
    context.user_data["lr_offset"] = 0
    msg = await update.message.reply_text("Формую звіт...")
    return await show_land_page(msg, context)


async def show_land_page(msg, context: ContextTypes.DEFAULT_TYPE):
    offset = context.user_data.get("lr_offset", 0)
    rows = await get_land_report_rows(
        context.user_data.get("lr_payer"),
        context.user_data.get("lr_company"),
        context.user_data.get("lr_contract"),
        context.user_data.get("lr_cadaster"),
        context.user_data.get("lr_field"),
        context.user_data.get("lr_area_from"),
        context.user_data.get("lr_area_to"),
        context.user_data.get("lr_ngo_from"),
        context.user_data.get("lr_ngo_to"),
        context.user_data.get("lr_end_date"),
        limit=PAGE_SIZE + 1,
        offset=offset,
    )
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    lines: list[str] = []
    for r in rows:
        rent = format_money(r["rent_amount"]) if r.get("rent_amount") else "—"
        ngo = format_money(r["ngo"]) if r.get("ngo") else "—"
        end_date = r.get("date_valid_to")
        end_str = end_date.strftime("%d.%m.%Y") if end_date else "—"
        lines.append(
            f"📍 {r['cadaster']}\n"
            f"📏 {r['area']:.4f} га | НГО {ngo} | 💰 {rent}\n"
            f"👤 {r.get('payer_name') or '—'} | 📄 {r.get('contract_number') or '—'} ({r.get('company_name') or '—'})\n"
            f"🌾 Поле: {r.get('field_name') or '—'}\n"
            f"📆 До: {end_str}"
        )
    if not lines:
        lines.append("Немає даних.")
    kb = report_nav_kb(offset > 0, has_next)
    await msg.edit_text("\n\n".join(lines), reply_markup=kb)
    return LR_SHOW


@admin_only
async def land_page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    direction = query.data.split("_")[1]
    offset = context.user_data.get("lr_offset", 0)
    if direction == "next":
        offset += PAGE_SIZE
    else:
        offset = max(0, offset - PAGE_SIZE)
    context.user_data["lr_offset"] = offset
    return await show_land_page(query.message, context)


@admin_only
async def land_export_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    rows = await get_land_report_rows(
        context.user_data.get("lr_payer"),
        context.user_data.get("lr_company"),
        context.user_data.get("lr_contract"),
        context.user_data.get("lr_cadaster"),
        context.user_data.get("lr_field"),
        context.user_data.get("lr_area_from"),
        context.user_data.get("lr_area_to"),
        context.user_data.get("lr_ngo_from"),
        context.user_data.get("lr_ngo_to"),
        context.user_data.get("lr_end_date"),
    )
    bio = await land_report_to_excel(rows)
    await query.message.reply_document(document=InputFile(bio, filename="land_report.xlsx"))
    await query.answer()
    return LR_SHOW


land_report_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📍 Звіт по ділянках$"), land_report_start)],
    states={
        LR_PAYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_payer)],
        LR_COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_company)],
        LR_CONTRACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_contract)],
        LR_CADASTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_cadaster)],
        LR_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_field)],
        LR_AREA_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_area_from)],
        LR_AREA_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_area_to)],
        LR_NGO_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_ngo_from)],
        LR_NGO_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_ngo_to)],
        LR_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_set_end_date)],
        LR_SHOW: [
            CallbackQueryHandler(land_page_cb, pattern=r"^payrep_(next|prev)$"),
            CallbackQueryHandler(land_export_cb, pattern=r"^payrep_export$"),
        ],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
