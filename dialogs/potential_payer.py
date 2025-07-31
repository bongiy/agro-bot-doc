"""Dialogs for managing potential landowners."""
import re
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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

from utils.fsm_navigation import (
    BACK_BTN,
    CANCEL_BTN,
    back_cancel_keyboard,
    push_state,
    handle_back_cancel,
    cancel_handler,
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


async def show_potential_payers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from keyboards.menu import crm_potential_menu
    await update.message.reply_text(
        "Меню «Потенційні пайовики»",
        reply_markup=crm_potential_menu,
    )
    return ConversationHandler.END

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

# States for filtering potential payers
(FILTER_MENU, FILTER_VILLAGE, FILTER_STATUS, FILTER_DATE,
 SEARCH_MENU, SEARCH_FIO, SEARCH_ID, SEARCH_CAD) = range(100, 108)


def normalize_phone(text: str | None):
    if not text:
        return None
    text = text.strip().replace(" ", "").replace("-", "")
    if re.fullmatch(r"0\d{9}", text):
        return "+38" + text
    if re.fullmatch(r"\+380\d{9}", text):
        return text
    return None


def normalize_cadastre(text: str) -> str:
    """Normalize cadastre number by inserting colons if missing."""
    raw = re.sub(r"\s", "", text)
    if ":" in raw:
        return raw
    digits = re.sub(r"\D", "", raw)
    parts = []
    if len(digits) > 10:
        parts.append(digits[:10])
        digits = digits[10:]
        if digits:
            parts.append(digits[:2])
            digits = digits[2:]
            if digits:
                parts.append(digits[:3])
                digits = digits[3:]
                if digits:
                    parts.append(digits)
    else:
        parts.append(digits)
    return ":".join([p for p in parts if p])


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["plots"] = []
    context.user_data["fsm_history"] = []
    push_state(context, FIO)
    await update.message.reply_text(
        "Введіть ПІБ потенційного пайовика:",
        reply_markup=back_cancel_keyboard,
    )
    return FIO


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
    context.user_data["full_name"] = update.message.text.strip()
    push_state(context, PHONE)
    await update.message.reply_text(
        "Введіть телефон (або пропустіть '-'):",
        reply_markup=back_cancel_keyboard,
    )
    return PHONE


async def get_village(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
    phone = normalize_phone(update.message.text)
    context.user_data["phone"] = phone
    push_state(context, VILLAGE)
    await update.message.reply_text(
        "Введіть назву села:", reply_markup=back_cancel_keyboard
    )
    return VILLAGE


async def get_area_est(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
    context.user_data["village"] = update.message.text.strip()
    push_state(context, AREA_EST)
    await update.message.reply_text(
        "Орієнтовна площа, га (можна пропустити '-'):",
        reply_markup=back_cancel_keyboard,
    )
    return AREA_EST


async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    try:
        area = float(text.replace(",", "."))
    except ValueError:
        area = None
    context.user_data["area_estimate"] = area
    push_state(context, NOTE)
    await update.message.reply_text(
        "Нотатка (можна пропустити '-'):", reply_markup=back_cancel_keyboard
    )
    return NOTE


async def ask_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
    note = update.message.text.strip()
    if note == "-":
        note = None
    context.user_data["note"] = note
    push_state(context, LAND_CAD)
    await update.message.reply_text(
        "Введіть кадастровий номер ділянки:", reply_markup=back_cancel_keyboard
    )
    return LAND_CAD


async def land_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
    cad = re.sub(r"\s", "", update.message.text)
    digits = re.sub(r"\D", "", cad)
    if len(digits) == 19:
        cad = f"{digits[:10]}:{digits[10:12]}:{digits[12:15]}:{digits[15:]}"
    context.user_data["cad"] = cad
    push_state(context, LAND_AREA)
    await update.message.reply_text(
        "Площа ділянки, га:", reply_markup=back_cancel_keyboard
    )
    return LAND_AREA


async def add_plot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, show_potential_payers_menu)
    if result is not None:
        return result
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
    push_state(context, ADD_MORE)
    await update.message.reply_text("Додати ще ділянку?", reply_markup=keyboard)
    return ADD_MORE


async def add_more_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    push_state(context, LAND_CAD)
    await query.message.reply_text(
        "Введіть кадастровий номер ділянки:", reply_markup=back_cancel_keyboard
    )
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
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_potential_payers_menu))],
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

    from crm.events_integration import get_events_text, events_button
    events_block = await get_events_text("potential_payer", pp_id)
    text += "\n\n" + events_block

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Змінити статус", callback_data=f"pp_chst:{pp_id}")],
        [InlineKeyboardButton("🔄 Перевести в активні", callback_data=f"pp_conv:{pp_id}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"pp_del:{pp_id}")],
        [events_button("potential_payer", pp_id)],
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


async def delete_pp_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pp_id = int(query.data.split(":")[1])
    from db import get_user_by_tg_id
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    payer = await database.fetch_one(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == pp_id)
    )
    if not payer:
        await query.answer("Не знайдено", show_alert=True)
        return
    text = (
        f"Ви точно хочете видалити <b>{payer['full_name']}</b>?\n"
        "Цю дію не можна скасувати."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Так, видалити", callback_data=f"pp_delc:{pp_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"pp_card:{pp_id}")],
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def delete_pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pp_id = int(query.data.split(":")[1])
    from db import get_user_by_tg_id, log_delete
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    payer = await database.fetch_one(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == pp_id)
    )
    if not payer:
        await query.answer("Не знайдено", show_alert=True)
        return
    await database.execute(
        PotentialLandPlot.delete().where(PotentialLandPlot.c.potential_payer_id == pp_id)
    )
    await database.execute(PotentialPayer.delete().where(PotentialPayer.c.id == pp_id))
    await log_delete(update.effective_user.id, user["role"], "potential_payer", pp_id, payer["full_name"], "")
    await query.message.edit_text("✅ Запис успішно видалено")


potential_callbacks = [
    CallbackQueryHandler(card_cb, pattern=r"^pp_card:\d+$"),
    CallbackQueryHandler(list_cb, pattern=r"^pp_list$"),
    CallbackQueryHandler(status_menu, pattern=r"^pp_chst:\d+$"),
    CallbackQueryHandler(set_status, pattern=r"^pp_set:\d+:.+"),
    CallbackQueryHandler(convert_cb, pattern=r"^pp_conv:\d+$"),
    CallbackQueryHandler(delete_pp_prompt, pattern=r"^pp_del:\d+$"),
    CallbackQueryHandler(delete_pp, pattern=r"^pp_delc:\d+$"),
]

# === Фільтрація потенційних пайовиків ===

async def filter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏘 За селом", callback_data="filter_village")],
            [InlineKeyboardButton("📘 За статусом", callback_data="filter_status")],
            [InlineKeyboardButton("📅 За датою", callback_data="filter_date")],
            [InlineKeyboardButton("🔍 Пошук", callback_data="filter_search")],
        ]
    )
    await update.message.reply_text("Оберіть тип фільтру:", reply_markup=keyboard)
    return FILTER_MENU


async def filter_village_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Введіть назву села:")
    return FILTER_VILLAGE


async def filter_status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(s, callback_data=f"status:{s}")] for s in STATUS_CHOICES]
    await query.message.edit_text("Оберіть статус:", reply_markup=InlineKeyboardMarkup(keyboard))
    return FILTER_STATUS


async def filter_date_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Введіть дату у форматі ДД.ММ.РРРР:")
    return FILTER_DATE


async def do_filter_list(target, rows):
    msg = getattr(target, "message", target)
    if not rows:
        await msg.reply_text("Нічого не знайдено.")
        return
    for r in rows:
        btn = InlineKeyboardButton("Картка", callback_data=f"pp_card:{r['id']}")
        await msg.reply_text(
            f"{r['id']}. {r['full_name']} ({r['village'] or '-'})",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )


async def send_pp_card(msg, pp_id: int):
    payer = await database.fetch_one(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == pp_id)
    )
    if not payer:
        await msg.reply_text("Не знайдено")
        return
    plots = await database.fetch_all(
        sqlalchemy.select(PotentialLandPlot).where(
            PotentialLandPlot.c.potential_payer_id == pp_id
        )
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

    from crm.events_integration import get_events_text, events_button
    events_block = await get_events_text("potential_payer", pp_id)
    text += "\n\n" + events_block

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Змінити статус", callback_data=f"pp_chst:{pp_id}")],
        [InlineKeyboardButton("🔄 Перевести в активні", callback_data=f"pp_conv:{pp_id}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"pp_del:{pp_id}")],
        [events_button("potential_payer", pp_id)],
        [InlineKeyboardButton("⬅️ Назад", callback_data="pp_list")],
    ])
    await msg.reply_text(text, reply_markup=keyboard)


async def show_search_results(target, rows):
    msg = getattr(target, "message", target)
    if not rows:
        await msg.reply_text("Нічого не знайдено.")
        return
    if len(rows) == 1:
        await send_pp_card(msg, rows[0]["id"])
        return
    for r in rows:
        btn = InlineKeyboardButton("Картка", callback_data=f"pp_card:{r['id']}")
        await msg.reply_text(
            f"{r['id']}. {r['full_name']} ({r['village'] or '-'})",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )


async def filter_village_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    village = update.message.text.strip()
    rows = await database.fetch_all(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.village.ilike(f"%{village}%"))
    )
    await do_filter_list(update, rows)
    return ConversationHandler.END


async def filter_status_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    status = query.data.split(":", 1)[1]
    rows = await database.fetch_all(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.status == status)
    )
    await do_filter_list(query, rows)
    return ConversationHandler.END


async def filter_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        date = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Некоректна дата. Спробуйте ще:")
        return FILTER_DATE
    rows = await database.fetch_all(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.last_contact_date == date)
    )
    await do_filter_list(update, rows)
    return ConversationHandler.END


async def filter_search_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔡 За ПІБ", callback_data="search_fio")],
        [InlineKeyboardButton("🆔 За ID", callback_data="search_id")],
        [InlineKeyboardButton("📍 За кадастровим номером", callback_data="search_cad")],
    ])
    await query.message.edit_text("Оберіть тип пошуку:", reply_markup=keyboard)
    return SEARCH_MENU


async def search_fio_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Введіть ПІБ або його частину:")
    return SEARCH_FIO


async def search_id_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Введіть ID:")
    return SEARCH_ID


async def search_cad_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Введіть кадастровий номер:")
    return SEARCH_CAD


async def search_fio_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    rows = await database.fetch_all(
        sqlalchemy.select(PotentialPayer).where(
            PotentialPayer.c.full_name.ilike(f"%{text}%")
        )
    )
    await show_search_results(update, rows)
    return ConversationHandler.END


async def search_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Некоректний ID. Спробуйте ще:")
        return SEARCH_ID
    pid = int(text)
    row = await database.fetch_one(
        sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == pid)
    )
    rows = [row] if row else []
    await show_search_results(update, rows)
    return ConversationHandler.END


async def search_cad_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cad = normalize_cadastre(update.message.text)
    pattern = f"%{cad}%"
    rows = await database.fetch_all(
        sqlalchemy.select(PotentialPayer)
        .join(PotentialLandPlot, PotentialLandPlot.c.potential_payer_id == PotentialPayer.c.id)
        .where(PotentialLandPlot.c.cadastre.ilike(pattern))
        .distinct()
    )
    await show_search_results(update, rows)
    return ConversationHandler.END


filter_potential_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔍 Фільтр$"), filter_start)],
    states={
        FILTER_MENU: [
            CallbackQueryHandler(filter_village_cb, pattern="^filter_village$"),
            CallbackQueryHandler(filter_status_cb, pattern="^filter_status$"),
            CallbackQueryHandler(filter_date_cb, pattern="^filter_date$"),
            CallbackQueryHandler(filter_search_cb, pattern="^filter_search$"),
        ],
        FILTER_VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_village_input)],
        FILTER_STATUS: [CallbackQueryHandler(filter_status_select, pattern=r"^status:.+")],
        FILTER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_date_input)],
        SEARCH_MENU: [
            CallbackQueryHandler(search_fio_cb, pattern="^search_fio$"),
            CallbackQueryHandler(search_id_cb, pattern="^search_id$"),
            CallbackQueryHandler(search_cad_cb, pattern="^search_cad$"),
        ],
        SEARCH_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_fio_input)],
        SEARCH_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_id_input)],
        SEARCH_CAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_cad_input)],
    },
    fallbacks=[],
)
