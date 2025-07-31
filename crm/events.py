"""CRM events module for planning and reminders."""

from datetime import datetime, time

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
    CRMEvent,
    Payer,
    PotentialPayer,
    Contract,
    LandPlot,
    LandPlotOwner,
)
from utils.fsm_navigation import (
    BACK_BTN,
    CANCEL_BTN,
    back_cancel_keyboard,
    push_state,
    handle_back_cancel,
    cancel_handler,
)

(
    CAT,
    PERSON_CHOOSE,
    PERSON_ID,
    TARGET_CHOOSE,
    CONTRACT_CHOOSE,
    LAND_CHOOSE,
    DATE_INPUT,
    TYPE_CHOOSE,
    COMMENT_INPUT,
) = range(9)

(
    FILTER_MENU,
    FILTER_DATE,
    FILTER_PAYER,
    FILTER_CONTRACT,
    FILTER_LAND,
) = range(100, 105)

EVENT_TYPES = [
    "\U0001F4DE Зв’язатись",
    "\U0001F4C4 Підписання договору",
    "\U0001F4E4 Подати на реєстрацію",
    "\U0001F4EC Контроль виплати",
    "\U0001F4DD Інше",
]

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from keyboards.menu import crm_events_menu
    await update.message.reply_text(
        "Меню «Планування і нагадування»",
        reply_markup=crm_events_menu,
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["fsm_history"] = []
    push_state(context, CAT)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Потенційний пайовик", callback_data="cat:pot")],
            [InlineKeyboardButton("Поточний пайовик", callback_data="cat:cur")],
        ]
    )
    await update.message.reply_text("👤 До кого стосується подія?", reply_markup=kb)
    return CAT

async def category_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat = query.data.split(":")[1]
    context.user_data["category"] = cat
    push_state(context, PERSON_CHOOSE)
    if cat == "pot":
        rows = await database.fetch_all(
            sqlalchemy.select(PotentialPayer).order_by(PotentialPayer.c.id.desc()).limit(5)
        )
        keyboard = [[InlineKeyboardButton(f"{r['id']}: {r['full_name']}", callback_data=f"person:{r['id']}")] for r in rows]
    else:
        rows = await database.fetch_all(
            sqlalchemy.select(Payer).order_by(Payer.c.id.desc()).limit(5)
        )
        keyboard = [[InlineKeyboardButton(f"{r['id']}: {r['name']}", callback_data=f"person:{r['id']}")] for r in rows]
    keyboard.append([InlineKeyboardButton("🔎 Пошук", callback_data="manual")])
    keyboard.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
    await query.message.edit_text("Оберіть особу:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PERSON_CHOOSE

async def person_choose_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        return await add_start(query, context)
    if data == "manual":
        push_state(context, PERSON_ID)
        await query.message.reply_text(
            "Введіть ID або частину ПІБ:", reply_markup=back_cancel_keyboard
        )
        return PERSON_ID
    pid = int(data.split(":")[1])
    context.user_data["person_id"] = pid
    context.user_data["entity_type"] = "potential_payer" if context.user_data["category"] == "pot" else "payer"
    return await after_person_chosen(query.message, context)

async def person_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, show_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    table = PotentialPayer if context.user_data.get("category") == "pot" else Payer
    from crm.potential_payer_flexible_search import search_potential_payers

    rows = await search_potential_payers(text) if context.user_data.get("category") == "pot" else None
    if rows is None:
        # current payers search by ID only
        if not text.isdigit():
            await update.message.reply_text("Введіть числовий ID:")
            return PERSON_ID
        pid = int(text)
        row = await database.fetch_one(sqlalchemy.select(table).where(table.c.id == pid))
        rows = [row] if row else []
    if not rows:
        await update.message.reply_text("Не знайдено. Спробуйте ще:")
        return PERSON_ID
    if len(rows) == 1:
        pid = rows[0]["id"]
        context.user_data["person_id"] = pid
        context.user_data["entity_type"] = (
            "potential_payer" if context.user_data.get("category") == "pot" else "payer"
        )
        return await after_person_chosen(update.message, context)
    keyboard = [
        [
            InlineKeyboardButton(
                f"\U0001F464 {r['full_name']} (ID: {r['id']})",
                callback_data=f"person:{r['id']}",
            )
        ]
        for r in rows[:10]
    ]
    keyboard.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
    await update.message.reply_text(
        "Оберіть пайовика:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PERSON_CHOOSE

async def after_person_chosen(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get("category") == "cur":
        push_state(context, TARGET_CHOOSE)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Лише пайовик", callback_data="target:payer")],
            [InlineKeyboardButton("📜 Договір", callback_data="target:contract")],
            [InlineKeyboardButton("📍 Ділянка", callback_data="target:land")],
            [InlineKeyboardButton(BACK_BTN, callback_data="back")],
        ])
        await msg.reply_text("Прив'язати подію до:", reply_markup=kb)
        return TARGET_CHOOSE
    else:
        push_state(context, DATE_INPUT)
        await msg.reply_text(
            "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
            reply_markup=back_cancel_keyboard,
        )
        return DATE_INPUT

async def target_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        return await category_cb(update, context)
    target = data.split(":")[1]
    if target == "payer":
        context.user_data["entity_type"] = "payer"
        context.user_data["entity_id"] = context.user_data.get("person_id")
        push_state(context, DATE_INPUT)
        await query.message.reply_text(
            "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
            reply_markup=back_cancel_keyboard,
        )
        return DATE_INPUT
    if target == "contract":
        rows = await database.fetch_all(
            sqlalchemy.select(Contract).where(Contract.c.payer_id == context.user_data.get("person_id"))
        )
        if not rows:
            await query.message.edit_text("Немає договорів. Подія буде прив'язана до пайовика.")
            context.user_data["entity_type"] = "payer"
            context.user_data["entity_id"] = context.user_data.get("person_id")
            push_state(context, DATE_INPUT)
            await query.message.reply_text(
                "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
                reply_markup=back_cancel_keyboard,
            )
            return DATE_INPUT
        push_state(context, CONTRACT_CHOOSE)
        kb = [[InlineKeyboardButton(f"{r['id']}: {r['number']}", callback_data=f"contract:{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
        await query.message.edit_text("Оберіть договір:", reply_markup=InlineKeyboardMarkup(kb))
        return CONTRACT_CHOOSE
    if target == "land":
        rows = await database.fetch_all(
            sqlalchemy.select(LandPlot)
            .join(LandPlotOwner, LandPlot.c.id == LandPlotOwner.c.land_plot_id)
            .where(LandPlotOwner.c.payer_id == context.user_data.get("person_id"))
        )
        if not rows:
            await query.message.edit_text("Немає ділянок. Подія буде прив'язана до пайовика.")
            context.user_data["entity_type"] = "payer"
            context.user_data["entity_id"] = context.user_data.get("person_id")
            push_state(context, DATE_INPUT)
            await query.message.reply_text(
                "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
                reply_markup=back_cancel_keyboard,
            )
            return DATE_INPUT
        push_state(context, LAND_CHOOSE)
        kb = [[InlineKeyboardButton(f"{r['id']}: {r['cadaster']}", callback_data=f"land:{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
        await query.message.edit_text("Оберіть ділянку:", reply_markup=InlineKeyboardMarkup(kb))
        return LAND_CHOOSE
    return TARGET_CHOOSE

async def contract_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "back":
        return await target_cb(update, context)
    cid = int(query.data.split(":")[1])
    context.user_data["entity_type"] = "contract"
    context.user_data["entity_id"] = cid
    push_state(context, DATE_INPUT)
    await query.message.edit_text("Обрано договір.")
    await query.message.reply_text(
        "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
        reply_markup=back_cancel_keyboard,
    )
    return DATE_INPUT

async def land_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "back":
        return await target_cb(update, context)
    lid = int(query.data.split(":")[1])
    context.user_data["entity_type"] = "land"
    context.user_data["entity_id"] = lid
    push_state(context, DATE_INPUT)
    await query.message.edit_text("Обрано ділянку.")
    await query.message.reply_text(
        "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
        reply_markup=back_cancel_keyboard,
    )
    return DATE_INPUT

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, show_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    try:
        event_dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        try:
            d = datetime.strptime(text, "%d.%m.%Y").date()
            event_dt = datetime.combine(d, time(hour=9, minute=0))
        except ValueError:
            await update.message.reply_text("Некоректна дата. Спробуйте ще:")
            return DATE_INPUT
    context.user_data["event_datetime"] = event_dt
    push_state(context, TYPE_CHOOSE)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(t, callback_data=f"etype:{i}")] for i, t in enumerate(EVENT_TYPES)] +
        [[InlineKeyboardButton(BACK_BTN, callback_data="back")]]
    )
    await update.message.reply_text("Оберіть тип події:", reply_markup=kb)
    return TYPE_CHOOSE

async def type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "back":
        await query.message.reply_text(
            "Введіть дату та час події (ДД.ММ.РРРР ГГ:ХХ). Якщо час не вказано, буде 09:00",
            reply_markup=back_cancel_keyboard,
        )
        return DATE_INPUT
    idx = int(query.data.split(":")[1])
    context.user_data["event_type"] = EVENT_TYPES[idx]
    push_state(context, COMMENT_INPUT)
    await query.message.edit_text("Введіть коментар або '-' щоб пропустити:")
    return COMMENT_INPUT

async def save_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, show_menu)
    if result is not None:
        return result
    comment = update.message.text.strip()
    if comment == "-":
        comment = ""
    await database.execute(
        CRMEvent.insert().values(
            entity_type=context.user_data.get("entity_type"),
            entity_id=context.user_data.get("entity_id", context.user_data.get("person_id")),
            event_datetime=context.user_data.get("event_datetime"),
            event_type=context.user_data.get("event_type"),
            comment=comment,
            status="planned",
            created_at=datetime.utcnow(),
            created_by_user_id=update.effective_user.id,
            reminder_status={"daily": False, "1h": False, "now": False},
        )
    )
    context.user_data.clear()
    from keyboards.menu import crm_events_menu
    await update.message.reply_text("✅ Подію збережено.", reply_markup=crm_events_menu)
    return ConversationHandler.END

add_event_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати подію$"), add_start)],
    states={
        CAT: [CallbackQueryHandler(category_cb, pattern=r"^cat:(pot|cur)$")],
        PERSON_CHOOSE: [CallbackQueryHandler(person_choose_cb, pattern=r"^(person:\d+|manual|back)$")],
        PERSON_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, person_id_input)],
        TARGET_CHOOSE: [CallbackQueryHandler(target_cb, pattern=r"^(target:(payer|contract|land)|back)$")],
        CONTRACT_CHOOSE: [CallbackQueryHandler(contract_cb, pattern=r"^(contract:\d+|back)$")],
        LAND_CHOOSE: [CallbackQueryHandler(land_cb, pattern=r"^(land:\d+|back)$")],
        DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_date)],
        TYPE_CHOOSE: [CallbackQueryHandler(type_cb, pattern=r"^(etype:\d+|back)$")],
        COMMENT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_comment)],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_menu))],
)

async def list_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("\U0001F4C5 За датою", callback_data="f:date")],
            [InlineKeyboardButton("\U0001F464 За пайовиком", callback_data="f:payer")],
            [InlineKeyboardButton("\U0001F4DC За договором", callback_data="f:contract")],
            [InlineKeyboardButton("\U0001F4CD За ділянкою", callback_data="f:land")],
        ]
    )
    await update.message.reply_text("🔍 Оберіть фільтр:", reply_markup=kb)
    return FILTER_MENU

async def filter_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ftype = query.data.split(":")[1]
    if ftype == "date":
        await query.message.edit_text("Введіть дату (ДД.ММ.РРРР):")
        return FILTER_DATE
    if ftype == "payer":
        await query.message.edit_text("Введіть ID пайовика:")
        context.user_data["filter_state"] = FILTER_PAYER
        return FILTER_PAYER
    if ftype == "contract":
        await query.message.edit_text("Введіть ID договору:")
        context.user_data["filter_state"] = FILTER_CONTRACT
        return FILTER_CONTRACT
    if ftype == "land":
        await query.message.edit_text("Введіть ID ділянки:")
        context.user_data["filter_state"] = FILTER_LAND
        return FILTER_LAND
    return FILTER_MENU

async def _show_rows(msg, rows):
    if not rows:
        await msg.reply_text("Подій не знайдено.")
        return
    for r in rows:
        text = await format_event(r)
        await msg.reply_text(text)

async def filter_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, show_menu)
    if result is not None:
        return result
    try:
        d = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Некоректна дата. Спробуйте ще:")
        return FILTER_DATE
    rows = await database.fetch_all(
        sqlalchemy.select(CRMEvent)
        .where(sqlalchemy.func.date(CRMEvent.c.event_datetime) == d)
        .order_by(CRMEvent.c.event_datetime)
    )
    await _show_rows(update.message, rows)
    return ConversationHandler.END

async def filter_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, show_menu)
    if result is not None:
        return result
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Введіть числовий ID:")
        return context.user_data.get("filter_state")
    iid = int(text)
    state = context.user_data.get("filter_state")
    if state == FILTER_PAYER:
        rows = await database.fetch_all(
            sqlalchemy.select(CRMEvent).where(CRMEvent.c.entity_type == "payer", CRMEvent.c.entity_id == iid)
        )
    elif state == FILTER_CONTRACT:
        rows = await database.fetch_all(
            sqlalchemy.select(CRMEvent).where(CRMEvent.c.entity_type == "contract", CRMEvent.c.entity_id == iid)
        )
    else:
        rows = await database.fetch_all(
            sqlalchemy.select(CRMEvent).where(CRMEvent.c.entity_type == "land", CRMEvent.c.entity_id == iid)
        )
    await _show_rows(update.message, rows)
    return ConversationHandler.END

async def format_event(row) -> str:
    if row["entity_type"] == "payer":
        p = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == row["entity_id"]))
        entity = f"\U0001F464 {p['name']} (поточний)" if p else f"ID {row['entity_id']}"
    elif row["entity_type"] == "potential_payer":
        p = await database.fetch_one(sqlalchemy.select(PotentialPayer).where(PotentialPayer.c.id == row["entity_id"]))
        entity = f"\U0001F464 {p['full_name']} (потенційний)" if p else f"ID {row['entity_id']}"
    elif row["entity_type"] == "contract":
        c = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == row["entity_id"]))
        entity = f"\U0001F4DC Договір №{c['number']}" if c else f"ID {row['entity_id']}"
    else:
        land = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == row["entity_id"]))
        entity = f"\U0001F4CD {land['cadaster']}" if land else f"ID {row['entity_id']}"
    d = row["event_datetime"].strftime("%d.%m.%Y %H:%M")
    txt = f"\U0001F4C5 {d} — {row['event_type']}\n{entity}\n\U0001F4DD {row['comment'] or '-'}"
    return txt

list_events_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📋 Переглянути події$"), list_start)],
    states={
        FILTER_MENU: [CallbackQueryHandler(filter_menu_cb, pattern=r"^f:(date|payer|contract|land)$")],
        FILTER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_date_input)],
        FILTER_PAYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_id_input)],
        FILTER_CONTRACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_id_input)],
        FILTER_LAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_id_input)],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler(show_menu))],
)
