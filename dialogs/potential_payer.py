"""Dialogs for managing potential landowners."""
import re
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import sqlalchemy

from db import (
    database,
    PotentialPayer,
    PotentialLandPlot,
    Payer,
    LandPlot,
)

# --- Statuses ---
STATUS_NEW = "🆕 Новий"
STATUS_IN_CONTACT = "☎️ В контакті"
STATUS_PREPARING = "📄 Готується договір"
STATUS_REFUSED = "❌ Відмова"
STATUS_SIGNED = "✅ Підписано"

STATUS_CHOICES = [
    STATUS_NEW,
    STATUS_IN_CONTACT,
    STATUS_PREPARING,
    STATUS_REFUSED,
    STATUS_SIGNED,
]

# --- FSM states ---
(
    FIO,
    PHONE,
    VILLAGE,
    AREA_EST,
    NOTE,
    LAND_CAD,
    LAND_AREA,
    ADD_MORE,
) = range(8)


def normalize_phone(text: str | None):
    if not text:
        return None
    text = text.strip().replace(" ", "").replace("-", "")
    if re.fullmatch(r"0\d{9}", text):
        return "+38" + text
    if re.fullmatch(r"\+380\d{9}", text):
        return text
    return None


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["plots"] = []
    await update.message.reply_text(
        "Введіть ПІБ потенційного пайовика:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return FIO


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Введіть телефон (або пропустіть '-'):")
    return PHONE


async def get_village(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = normalize_phone(update.message.text)
    context.user_data["phone"] = phone
    await update.message.reply_text("Введіть назву села:")
    return VILLAGE


async def get_area_est(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["village"] = update.message.text.strip()
    await update.message.reply_text("Орієнтовна площа, га (можна пропустити '-'):")
    return AREA_EST


async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        area = float(text.replace(",", "."))
    except ValueError:
        area = None
    context.user_data["area_estimate"] = area
    await update.message.reply_text("Нотатка (можна пропустити '-'):")
    return NOTE


async def ask_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    if note == "-":
        note = None
    context.user_data["note"] = note
    await update.message.reply_text("Введіть кадастровий номер ділянки:")
    return LAND_CAD


async def land_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cad = re.sub(r"\s", "", update.message.text)
    digits = re.sub(r"\D", "", cad)
    if len(digits) == 19:
        cad = f"{digits[:10]}:{digits[10:12]}:{digits[12:15]}:{digits[15:]}"
    context.user_data["cad"] = cad
    await update.message.reply_text("Площа ділянки, га:")
    return LAND_AREA


async def add_plot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        area = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Некоректна площа. Введіть ще раз:")
        return LAND_AREA
    context.user_data["plots"].append({"cadastre": context.user_data.get("cad"), "area": area})
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Додати ділянку", callback_data="add_more")],
            [InlineKeyboardButton("✅ Завершити", callback_data="finish")],
        ]
    )
    await update.message.reply_text("Додати ще ділянку?", reply_markup=keyboard)
    return ADD_MORE


async def add_more_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Введіть кадастровий номер ділянки:")
    return LAND_CAD


async def finish_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = {
        "full_name": context.user_data.get("full_name"),
        "phone": context.user_data.get("phone"),
        "village": context.user_data.get("village"),
        "area_estimate": context.user_data.get("area_estimate"),
        "note": context.user_data.get("note"),
        "status": STATUS_NEW,
        "last_contact_date": datetime.utcnow().date(),
    }
    payer_id = await database.execute(PotentialPayer.insert().values(**data))
    rows = [
        {"potential_payer_id": payer_id, "cadastre": p["cadastre"], "area": p["area"]}
        for p in context.user_data.get("plots", [])
    ]
    if rows:
        await database.execute_many(PotentialLandPlot.insert(), rows)
    await query.message.edit_text("✅ Запис створено")
    return ConversationHandler.END


add_potential_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати$"), add_start)],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_village)],
        VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_area_est)],
        AREA_EST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_note)],
        NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_land)],
        LAND_CAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_area)],
        LAND_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plot)],
        ADD_MORE: [
            CallbackQueryHandler(add_more_cb, pattern="^add_more$"),
            CallbackQueryHandler(finish_cb, pattern="^finish$"),
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^◀️ Назад$"), lambda u, c: ConversationHandler.END)],
)


async def list_potential(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await database.fetch_all(sqlalchemy.select(PotentialPayer))
    if not rows:
        await update.message.reply_text("Список порожній")
        return
    for r in rows:
        btn = InlineKeyboardButton("Картка", callback_data=f"pp_card:{r['id']}")
        await update.message.reply_text(
            f"{r['id']}. {r['full_name']} ({r['village'] or '-'})",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )


async def card_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pp_id = int(query.data.split(":")[1])
    payer = await database.fetch_one(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == pp_id)
    )
    if not payer:
        await query.answer("Не знайдено", show_alert=True)
        return
    plots = await database.fetch_all(
        sqlalchemy.select(PotentialLandPlot).where(PotentialLandPlot.c.potential_payer_id == pp_id)
    )
    plots_txt = "\n".join(
        [f"   ├ {p['cadastre']} — {p['area']:.4f} га" for p in plots]
    ) or "—"
    text = (
        f"👤 ПІБ: {payer['full_name']}\n"
        f"📞 Телефон: {payer['phone'] or '-'}\n"
        f"🏘 Село: {payer['village'] or '-'}\n"
        f"📏 Орієнтовна площа: {payer['area_estimate'] or '-'} га\n"
        f"📍 Ділянки:\n{plots_txt}\n"
        f"📝 Нотатка: {payer['note'] or '-'}\n"
        f"📅 Останній контакт: {payer['last_contact_date'] or '-'}\n"
        f"📘 Статус: {payer['status']}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Змінити статус", callback_data=f"pp_chst:{pp_id}")],
        [InlineKeyboardButton("🔄 Перевести в активні", callback_data=f"pp_conv:{pp_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="pp_list")],
    ])
    await query.message.edit_text(text, reply_markup=keyboard)


async def list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await list_potential(update, context)


async def status_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pp_id = int(query.data.split(":")[1])
    keyboard = [[InlineKeyboardButton(s, callback_data=f"pp_set:{pp_id}:{s}")] for s in STATUS_CHOICES]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"pp_card:{pp_id}")])
    await query.message.edit_text("Оберіть статус:", reply_markup=InlineKeyboardMarkup(keyboard))


async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, pp_id, status = query.data.split(":", 2)
    pp_id = int(pp_id)
    await database.execute(
        PotentialPayer.update()
        .where(PotentialPayer.c.id == pp_id)
        .values(status=status, last_contact_date=datetime.utcnow().date())
    )
    await card_cb(update, context)


async def convert_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pp_id = int(query.data.split(":")[1])
    payer = await database.fetch_one(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == pp_id)
    )
    if not payer:
        await query.answer("Не знайдено", show_alert=True)
        return
    plots = await database.fetch_all(
        sqlalchemy.select(PotentialLandPlot).where(PotentialLandPlot.c.potential_payer_id == pp_id)
    )
    new_id = await database.execute(
        Payer.insert().values(name=payer["full_name"], phone=payer["phone"], selo=payer["village"])
    )
    for p in plots:
        await database.execute(
            LandPlot.insert().values(cadaster=p["cadastre"], area=p["area"], payer_id=new_id)
        )
    await database.execute(PotentialLandPlot.delete().where(PotentialLandPlot.c.potential_payer_id == pp_id))
    await database.execute(PotentialPayer.delete().where(PotentialPayer.c.id == pp_id))
    await query.message.edit_text("✅ Переведено в активні")


potential_callbacks = [
    CallbackQueryHandler(card_cb, pattern=r"^pp_card:\d+$"),
    CallbackQueryHandler(list_cb, pattern=r"^pp_list$"),
    CallbackQueryHandler(status_menu, pattern=r"^pp_chst:\d+$"),
    CallbackQueryHandler(set_status, pattern=r"^pp_set:\d+:.+"),
    CallbackQueryHandler(convert_cb, pattern=r"^pp_conv:\d+$"),
]
