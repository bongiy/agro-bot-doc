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
from db import get_rent_summary
from keyboards.reports import rent_status_filter_kb, report_nav_kb
from utils.reports import rent_summary_to_excel
from contract_generation_v2 import format_money

RENT_YEAR, RENT_COMPANY, RENT_STATUS, RENT_SHOW = range(4)
PAGE_SIZE = 10


@admin_only
async def rent_summary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть рік:")
    return RENT_YEAR


@admin_only
async def rent_set_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        year = int(text)
    except ValueError:
        await update.message.reply_text("Введіть рік числом:")
        return RENT_YEAR
    context.user_data["rent_year"] = year
    await update.message.reply_text("Введіть назву компанії або '-' для всіх:")
    return RENT_COMPANY


@admin_only
async def rent_set_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["rent_company"] = None if text == "-" else text
    await update.message.reply_text("Оберіть статус:", reply_markup=rent_status_filter_kb())
    return RENT_STATUS


@admin_only
async def rent_set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    status = query.data.split(":")[1]
    context.user_data["rent_status"] = None if status == "any" else status
    context.user_data["rent_offset"] = 0
    await query.message.edit_text("Формую звіт...")
    return await show_rent_page(query.message, context)


async def show_rent_page(msg, context: ContextTypes.DEFAULT_TYPE):
    offset = context.user_data.get("rent_offset", 0)
    rows = await get_rent_summary(
        context.user_data["rent_year"],
        context.user_data.get("rent_company"),
        context.user_data.get("rent_status"),
        limit=PAGE_SIZE + 1,
        offset=offset,
    )
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    lines: list[str] = []
    for r in rows:
        rent_total = float(r["rent_total"] or 0)
        paid_total = float(r["paid_total"] or 0)
        debt = rent_total - paid_total
        lines.append(
            (
                f"🏢 <b>{r['name']}</b>\n"
                f"Договорів: {r['contracts']} | Пайовиків: {r['payers']} | Ділянок: {r['plots']}\n"
                f"Нараховано: {format_money(rent_total)} | "
                f"Виплачено: {format_money(paid_total)} | "
                f"Борг: {format_money(debt)}\n"
                f"Очікує: {format_money(float(r['pending_amount'] or 0))} | "
                f"Частково: {format_money(float(r['partial_amount'] or 0))} | "
                f"Оплачено: {format_money(float(r['paid_amount'] or 0))}"
            )
        )
    if not lines:
        lines.append("Немає даних.")
    kb = report_nav_kb(offset > 0, has_next)
    await msg.edit_text("\n\n".join(lines), reply_markup=kb, parse_mode="HTML")
    return RENT_SHOW


@admin_only
async def rent_page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    direction = query.data.split("_")[1]
    offset = context.user_data.get("rent_offset", 0)
    if direction == "next":
        offset += PAGE_SIZE
    else:
        offset = max(0, offset - PAGE_SIZE)
    context.user_data["rent_offset"] = offset
    return await show_rent_page(query.message, context)


@admin_only
async def rent_export_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    rows = await get_rent_summary(
        context.user_data["rent_year"],
        context.user_data.get("rent_company"),
        context.user_data.get("rent_status"),
    )
    bio = await rent_summary_to_excel(rows)
    await query.message.reply_document(
        document=InputFile(bio, filename="rent_summary.xlsx")
    )
    await query.answer()
    return RENT_SHOW


rent_summary_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^💰 Зведення по орендній платі$"), rent_summary_start)
    ],
    states={
        RENT_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, rent_set_year)],
        RENT_COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, rent_set_company)],
        RENT_STATUS: [CallbackQueryHandler(rent_set_status, pattern=r"^rent_status:")],
        RENT_SHOW: [
            CallbackQueryHandler(rent_page_cb, pattern=r"^payrep_(next|prev)$"),
            CallbackQueryHandler(rent_export_cb, pattern=r"^payrep_export$"),
        ],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
