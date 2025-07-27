from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler,
    CommandHandler, filters, ContextTypes
)
from db import get_company, update_company

EDIT_SELECT, EDIT_VALUE = range(2)

FIELDS = [
    ("opf", "ОПФ"),
    ("name", "Базова назва"),
    ("full_name", "Повна назва"),
    ("short_name", "Скорочена назва"),
    ("edrpou", "ЄДРПОУ"),
    ("bank_account", "р/р (IBAN)"),
    ("tax_group", "Група оподаткування"),
    ("is_vat_payer", "Платник ПДВ (Так/Ні)"),
    ("vat_ipn", "ІПН платника ПДВ"),
    ("address_legal", "Юридична адреса"),
    ("address_postal", "Поштова адреса"),
    ("director", "ПІБ директора"),
]

def _field_name(key: str) -> str:
    return dict(FIELDS)[key]

async def edit_company_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    company_id = int(query.data.split(":")[1])
    context.user_data["edit_company_id"] = company_id
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"edit_company_fsm:{company_id}:{key}")]
        for key, name in FIELDS
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"company_card:{company_id}")])
    await query.message.edit_text(
        "Оберіть поле для редагування:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_SELECT

async def edit_company_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, company_id, field_key = query.data.split(":")
    company_id = int(company_id)
    context.user_data["edit_company_id"] = company_id
    context.user_data["edit_company_field"] = field_key
    company = await get_company(company_id)
    old_value = company[field_key]
    if field_key == "is_vat_payer":
        display_old = "Так" if old_value else "Ні"
    else:
        display_old = old_value if old_value is not None else "(порожньо)"
    await query.message.edit_text(
        f"Поточне значення: <b>{display_old}</b>\n"
        f"Введіть нове значення для: {_field_name(field_key)}",
        parse_mode="HTML"
    )
    return EDIT_VALUE

async def edit_company_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    company_id = context.user_data.get("edit_company_id")
    field_key = context.user_data.get("edit_company_field")
    if field_key == "is_vat_payer":
        val = value.lower()
        if val in ("так", "1", "true", "yes"):
            value = True
        elif val in ("ні", "0", "false", "no"):
            value = False
        else:
            await update.message.reply_text('Введіть "Так" або "Ні"')
            return EDIT_VALUE
    await update_company(company_id, {field_key: value})
    await update.message.reply_text("✅ Зміни збережено!")
    return ConversationHandler.END

edit_company_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_company_menu, pattern=r"^company_edit:\d+$")],
    states={
        EDIT_SELECT: [
            CallbackQueryHandler(edit_company_input, pattern=r"^edit_company_fsm:\d+:\w+$"),
            CallbackQueryHandler(edit_company_menu, pattern=r"^company_edit:\d+$"),
        ],
        EDIT_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_company_save),
        ],
    },
    fallbacks=[CommandHandler("start", lambda u, c: None)],
)
