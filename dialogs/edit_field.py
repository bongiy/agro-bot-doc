from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters, ContextTypes
from db import database, Field

EDIT_SELECT, EDIT_VALUE = range(2)

FIELDS = [
    ("name", "Назва поля"),
    ("area_actual", "Фактична площа (га)"),
]

async def edit_field_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    field_id = int(query.data.split(":")[1])
    context.user_data["edit_field_id"] = field_id
    keyboard = [
        [InlineKeyboardButton(field_name, callback_data=f"edit_field_fsm:{field_id}:{field_key}")]
        for field_key, field_name in FIELDS
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"field_card:{field_id}")])
    await query.message.edit_text("Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_SELECT

async def edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, field_id, field_key = query.data.split(":")
    field_id = int(field_id)
    context.user_data["edit_field_id"] = field_id
    context.user_data["edit_field_key"] = field_key
    from db import Field
    select = Field.select().where(Field.c.id == field_id)
    field = await database.fetch_one(select)
    old_value = getattr(field, field_key, "")
    await query.message.edit_text(
        f"Поточне значення: <b>{old_value if old_value else '(порожньо)'}</b>\n"
        f"Введіть нове значення для: {dict(FIELDS)[field_key]}",
        parse_mode="HTML"
    )
    return EDIT_VALUE

async def edit_field_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    field_id = context.user_data.get("edit_field_id")
    field_key = context.user_data.get("edit_field_key")
    if field_key == "area_actual":
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Некоректна площа. Введіть число!")
            return EDIT_VALUE
    from db import Field
    query_db = Field.update().where(Field.c.id == field_id).values({field_key: value})
    await database.execute(query_db)
    await update.message.reply_text("✅ Зміни збережено!")
    return ConversationHandler.END

edit_field_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_field_menu, pattern=r"^edit_field:\d+$")],
    states={
        EDIT_SELECT: [
            CallbackQueryHandler(edit_field_input, pattern=r"^edit_field_fsm:\d+:\w+$"),
            CallbackQueryHandler(edit_field_menu, pattern=r"^edit_field:\d+$"),
        ],
        EDIT_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_save),
        ],
    },
    fallbacks=[CommandHandler("start", lambda u, c: None)],
)
