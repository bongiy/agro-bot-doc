from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
import sqlalchemy
from db import database, Payer, record_inheritance_debt
from dialogs.payer import normalize_bank_card

EDIT_SELECT, EDIT_VALUE = range(2)

FIELDS = [
    ("name", "ПІБ"),
    ("ipn", "ІПН"),
    ("oblast", "Область"),
    ("rayon", "Район"),
    ("selo", "Село"),
    ("vul", "Вулиця"),
    ("bud", "Будинок"),
    ("kv", "Квартира"),
    ("phone", "Телефон"),
    ("bank_card", "Картка для виплат"),
    ("doc_type", "Тип документа"),
    ("passport_series", "Серія паспорта"),
    ("passport_number", "Номер паспорта"),
    ("passport_issuer", "Ким виданий"),
    ("passport_date", "Коли виданий"),
    ("id_number", "ID-картка"),
    ("unzr", "УНЗР"),
    ("idcard_issuer", "Код підрозділу"),
    ("idcard_date", "Дата видачі ID"),
    ("birth_date", "Дата народження"),
]

async def edit_payer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    context.user_data["edit_payer_id"] = payer_id
    row = await database.fetch_one(
        sqlalchemy.select(Payer.c.is_deceased).where(Payer.c.id == payer_id)
    )
    status_btn = (
        "↩️ Зняти статус 'Помер'" if row and row["is_deceased"] else "🕯 Позначити як померлого"
    )
    keyboard = [
        [InlineKeyboardButton(status_btn, callback_data=f"toggle_deceased:{payer_id}")]
    ] + [
        [InlineKeyboardButton(field_name, callback_data=f"edit_field:{payer_id}:{field_key}")]
        for field_key, field_name in FIELDS
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"payer_card:{payer_id}")])
    await query.message.edit_text(
        "Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_SELECT

async def edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, payer_id, field_key = query.data.split(":")
    payer_id = int(payer_id)
    context.user_data["edit_payer_id"] = payer_id
    context.user_data["edit_field"] = field_key
    select = Payer.select().where(Payer.c.id == payer_id)
    payer = await database.fetch_one(select)
    old_value = getattr(payer, field_key, "")
    await query.message.edit_text(
        f"Поточне значення: <b>{old_value if old_value else '(порожньо)'}</b>\n"
        f"Введіть нове значення для поля: {dict(FIELDS)[field_key]}",
        parse_mode="HTML"
    )
    return EDIT_VALUE

async def edit_field_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    payer_id = context.user_data.get("edit_payer_id")
    field_key = context.user_data.get("edit_field")
    print(f"DEBUG: id={payer_id} key={field_key} value={value}")
    if field_key == "bank_card":
        if value != "-":
            card = normalize_bank_card(value)
            if not card:
                await update.message.reply_text("❗️ Введіть 16 або 19 цифр картки")
                return EDIT_VALUE
            value = card
        else:
            value = None
    query_db = Payer.update().where(Payer.c.id == payer_id).values({field_key: value})
    await database.execute(query_db)
    await update.message.reply_text("✅ Зміни збережено!")
    # Можна повертати до меню редагування або завершувати FSM:
    # return await edit_payer_menu_from_save(update, context)
    return ConversationHandler.END


async def toggle_deceased(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    row = await database.fetch_one(
        sqlalchemy.select(Payer.c.is_deceased).where(Payer.c.id == payer_id)
    )
    new_val = not bool(row["is_deceased"]) if row is not None else True
    await database.execute(
        Payer.update().where(Payer.c.id == payer_id).values(is_deceased=new_val)
    )
    if new_val:
        await record_inheritance_debt(payer_id)
    await query.answer("Статус оновлено")
    # Show updated menu
    query.data = f"edit_payer:{payer_id}"
    return await edit_payer_menu(update, context)

edit_payer_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_payer_menu, pattern=r"^edit_payer:\d+$")],
    states={
        EDIT_SELECT: [
            CallbackQueryHandler(edit_field_input, pattern=r"^edit_field:\d+:\w+$"),
            CallbackQueryHandler(toggle_deceased, pattern=r"^toggle_deceased:\d+$"),
            CallbackQueryHandler(edit_payer_menu, pattern=r"^edit_payer:\d+$"),
        ],
        EDIT_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_save),
        ],
    },
    fallbacks=[CommandHandler("start", lambda u, c: None)],
)
