"""FSM for managing counterparties in CRM."""

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
    User,
    add_counterparty,
    get_counterparties,
    search_counterparties,
    get_counterparty,
    update_counterparty,
    delete_counterparty,
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
    LIST,
    SEARCH_QUERY,
    CREATE_NAME,
    CREATE_EDRPOU,
    CREATE_DIRECTOR,
    CREATE_ADDRESS,
    CREATE_PHONE,
    CREATE_EMAIL,
    CREATE_NOTE,
    VIEW,
    EDIT_CHOOSE,
    EDIT_FIELD,
    DELETE_CONFIRM,
) = range(13)


async def _is_admin(user_id: int) -> bool:
    row = await database.fetch_one(
        sqlalchemy.select(User.c.role).where(User.c.telegram_id == user_id)
    )
    return bool(row and row["role"] == "admin")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["fsm_history"] = []
    push_state(context, LIST)
    rows = await get_counterparties()
    keyboard = [
        [
            InlineKeyboardButton(
                f"{r['name']} ({r['edrpou']})", callback_data=f"view:{r['id']}"
            )
        ]
        for r in rows[:5]
    ]
    keyboard.append([InlineKeyboardButton("➕ Додати", callback_data="add")])
    keyboard.append([InlineKeyboardButton("🔍 Пошук", callback_data="search")])
    await update.message.reply_text(
        "📒 Каталог контрагентів", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LIST


async def list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "add":
        push_state(context, CREATE_NAME)
        await query.message.reply_text("Введіть назву ТОВ:", reply_markup=back_cancel_keyboard)
        return CREATE_NAME
    if data == "search":
        push_state(context, SEARCH_QUERY)
        await query.message.reply_text("Введіть назву, ЄДРПОУ або директора:", reply_markup=back_cancel_keyboard)
        return SEARCH_QUERY
    if data.startswith("view:"):
        cid = int(data.split(":")[1])
        return await show_card(query.message, context, cid)
    return LIST


async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    text = update.message.text.strip()
    rows = await search_counterparties(text)
    if not rows:
        await update.message.reply_text("Не знайдено. Спробуйте ще:")
        return SEARCH_QUERY
    keyboard = [
        [InlineKeyboardButton(f"{r['name']} ({r['edrpou']})", callback_data=f"view:{r['id']}")]
        for r in rows
    ]
    keyboard.append([InlineKeyboardButton(BACK_BTN, callback_data="back")])
    await update.message.reply_text(
        "Оберіть контрагента:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LIST


async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["name"] = update.message.text.strip()
    push_state(context, CREATE_EDRPOU)
    await update.message.reply_text("Введіть ЄДРПОУ (8 цифр):", reply_markup=back_cancel_keyboard)
    return CREATE_EDRPOU


async def create_edrpou(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["edrpou"] = update.message.text.strip()
    push_state(context, CREATE_DIRECTOR)
    await update.message.reply_text("Введіть директора:", reply_markup=back_cancel_keyboard)
    return CREATE_DIRECTOR


async def create_director(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["director"] = update.message.text.strip()
    push_state(context, CREATE_ADDRESS)
    await update.message.reply_text("Введіть юридичну адресу:", reply_markup=back_cancel_keyboard)
    return CREATE_ADDRESS


async def create_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["legal_address"] = update.message.text.strip()
    push_state(context, CREATE_PHONE)
    await update.message.reply_text("Введіть телефон:", reply_markup=back_cancel_keyboard)
    return CREATE_PHONE


async def create_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["phone"] = update.message.text.strip()
    push_state(context, CREATE_EMAIL)
    await update.message.reply_text("Введіть email (опційно):", reply_markup=back_cancel_keyboard)
    return CREATE_EMAIL


async def create_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["email"] = update.message.text.strip()
    push_state(context, CREATE_NOTE)
    await update.message.reply_text("Примітка (опційно):", reply_markup=back_cancel_keyboard)
    return CREATE_NOTE


async def create_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    context.user_data["note"] = update.message.text.strip()
    cid = await add_counterparty(context.user_data)
    await update.message.reply_text(
        f"Контрагента додано (ID:{cid}).", reply_markup=ReplyKeyboardRemove()
    )
    return await start(update, context)


async def show_card(msg, context: ContextTypes.DEFAULT_TYPE, cid: int) -> int:
    row = await get_counterparty(cid)
    if not row:
        if msg.from_user and msg.from_user.id == context.bot.id:
            await msg.edit_text("Не знайдено.")
        else:
            await msg.reply_text("Не знайдено.")
        return LIST
    text = (
        f"<b>{row['name']}</b>\n"
        f"ЄДРПОУ: {row['edrpou']}\n"
        f"Директор: {row.get('director','')}\n"
        f"Адреса: {row.get('legal_address','')}\n"
        f"Телефон: {row.get('phone','')}\n"
        f"Email: {row.get('email','')}\n"
        f"Примітка: {row.get('note','')}"
    )
    kb = [[InlineKeyboardButton(BACK_BTN, callback_data="back")]]
    if await _is_admin(msg.chat_id if msg.chat_id else msg.from_user.id):
        kb.insert(0, [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit:{cid}")])
        kb.insert(1, [InlineKeyboardButton("🗑️ Видалити", callback_data=f"del:{cid}")])
    if msg.from_user and msg.from_user.id == context.bot.id:
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    context.user_data["current_id"] = cid
    push_state(context, VIEW)
    return VIEW


async def view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        return await start(query, context)
    if data.startswith("edit:"):
        cid = int(data.split(":")[1])
        context.user_data["current_id"] = cid
        push_state(context, EDIT_CHOOSE)
        kb = [
            [InlineKeyboardButton("Назва", callback_data="field:name")],
            [InlineKeyboardButton("ЄДРПОУ", callback_data="field:edrpou")],
            [InlineKeyboardButton("Директор", callback_data="field:director")],
            [InlineKeyboardButton("Адреса", callback_data="field:legal_address")],
            [InlineKeyboardButton("Телефон", callback_data="field:phone")],
            [InlineKeyboardButton("Email", callback_data="field:email")],
            [InlineKeyboardButton("Примітка", callback_data="field:note")],
            [InlineKeyboardButton(BACK_BTN, callback_data="back")],
        ]
        await query.message.edit_text(
            "Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return EDIT_CHOOSE
    if data.startswith("del:"):
        cid = int(data.split(":")[1])
        context.user_data["current_id"] = cid
        push_state(context, DELETE_CONFIRM)
        kb = [
            [InlineKeyboardButton("✅ Так", callback_data="confirm")],
            [InlineKeyboardButton(BACK_BTN, callback_data="back")],
        ]
        await query.message.edit_text(
            "Видалити контрагента?", reply_markup=InlineKeyboardMarkup(kb)
        )
        return DELETE_CONFIRM
    return VIEW


async def edit_choose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        cid = context.user_data.get("current_id")
        return await show_card(query.message, context, cid)
    if data.startswith("field:"):
        field = data.split(":")[1]
        context.user_data["edit_field"] = field
        push_state(context, EDIT_FIELD)
        await query.message.reply_text("Введіть нове значення:", reply_markup=back_cancel_keyboard)
        return EDIT_FIELD
    return EDIT_CHOOSE


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_cancel(update, context, start)
    if result is not None:
        return result
    field = context.user_data.get("edit_field")
    cid = context.user_data.get("current_id")
    value = update.message.text.strip()
    await update_counterparty(cid, {field: value})
    await update.message.reply_text("Збережено.", reply_markup=ReplyKeyboardRemove())
    return await show_card(update.message, context, cid)


async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "confirm":
        cid = context.user_data.get("current_id")
        await delete_counterparty(cid)
        await query.message.edit_text("Контрагента видалено.")
        return await start(query, context)
    if query.data == "back":
        cid = context.user_data.get("current_id")
        return await show_card(query.message, context, cid)
    return DELETE_CONFIRM


counterparty_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📒 Контрагенти$"), start)],
    states={
        LIST: [CallbackQueryHandler(list_cb)],
        SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
        CREATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
        CREATE_EDRPOU: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_edrpou)],
        CREATE_DIRECTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_director)],
        CREATE_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_address)],
        CREATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_phone)],
        CREATE_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_email)],
        CREATE_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_note)],
        VIEW: [CallbackQueryHandler(view_cb)],
        EDIT_CHOOSE: [CallbackQueryHandler(edit_choose)],
        EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
        DELETE_CONFIRM: [CallbackQueryHandler(delete_confirm)],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_handler)],
)
