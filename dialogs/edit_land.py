from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters, ContextTypes
from db import database, LandPlot, Field

EDIT_SELECT, EDIT_VALUE = range(2)

FIELDS = [
    ("cadaster", "Кадастровий номер"),
    ("area", "Площа (га)"),
    ("ngo", "НГО"),
    ("field_id", "Поле (id)"),
    ("region", "Область"),
    ("district", "Район"),
    ("council", "Сільрада"),
]

async def edit_land_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    context.user_data["edit_land_id"] = land_id
    keyboard = [
        [InlineKeyboardButton(field_name, callback_data=f"edit_land_fsm:{land_id}:{field_key}")]
        for field_key, field_name in FIELDS
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"land_card:{land_id}")])
    await query.message.edit_text("Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_SELECT

async def edit_land_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, land_id, field_key = query.data.split(":")
    land_id = int(land_id)
    context.user_data["edit_land_id"] = land_id
    context.user_data["edit_field_key"] = field_key
    from db import LandPlot
    select = LandPlot.select().where(LandPlot.c.id == land_id)
    land = await database.fetch_one(select)
    old_value = getattr(land, field_key, "")
    await query.message.edit_text(
        f"Поточне значення: <b>{old_value if old_value else '(порожньо)'}</b>\n"
        f"Введіть нове значення для: {dict(FIELDS)[field_key]}",
        parse_mode="HTML"
    )
    return EDIT_VALUE

async def edit_land_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    land_id = context.user_data.get("edit_land_id")
    field_key = context.user_data.get("edit_field_key")
    if field_key in ("area", "ngo"):
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Некоректне число. Введіть ще раз!")
            return EDIT_VALUE
    if field_key == "field_id":
        # Додатково можна підказувати список полів
        try:
            value = int(value)
        except ValueError:
            await update.message.reply_text("ID поля має бути числом!")
            return EDIT_VALUE
        # можна додати перевірку на існування такого поля
    from db import LandPlot
    query_db = LandPlot.update().where(LandPlot.c.id == land_id).values({field_key: value})
    await database.execute(query_db)
    await update.message.reply_text("✅ Зміни збережено!")
    return ConversationHandler.END

edit_land_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_land_menu, pattern=r"^edit_land:\d+$")],
    states={
        EDIT_SELECT: [
            CallbackQueryHandler(edit_land_input, pattern=r"^edit_land_fsm:\d+:\w+$"),
            CallbackQueryHandler(edit_land_menu, pattern=r"^edit_land:\d+$"),
        ],
        EDIT_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_land_save),
        ],
    },
    fallbacks=[CommandHandler("start", lambda u, c: None)],
)
