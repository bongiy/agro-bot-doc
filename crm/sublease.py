"""FSM for adding sublease with counterparty selection."""

from datetime import datetime
from typing import List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from db import (
    add_counterparty,
    get_counterparty,
    search_counterparties,
    update_counterparty,
    add_sublease,
)
from crm.counterparty import _is_admin

# conversation states
(
    CHOOSE_TYPE,
    COUNTERPARTY_SEARCH,
    COUNTERPARTY_RESULTS,
    COUNTERPARTY_VIEW,
    COUNTERPARTY_CREATE_NAME,
    COUNTERPARTY_CREATE_EDRPOU,
    COUNTERPARTY_CREATE_PHONE,
    COUNTERPARTY_EDIT_FIELD,
    COUNTERPARTY_EDIT_VALUE,
    LAND_PLOTS,
    CONFIRM,
) = range(11)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for sublease creation."""
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("🟢 Ми передаємо ділянки", callback_data="transfer")],
        [InlineKeyboardButton("🔵 Ми отримуємо ділянки", callback_data="receive")],
    ]
    await update.message.reply_text(
        "Оберіть тип суборенди:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_TYPE


async def type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["sublease_type"] = query.data
    await query.message.edit_text("Введіть назву або ЄДРПОУ контрагента:")
    return COUNTERPARTY_SEARCH


async def counterparty_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["cp_search"] = text
    rows = await search_counterparties(text)
    if not rows:
        kb = []
        if await _is_admin(update.effective_user.id):
            kb.append([InlineKeyboardButton("➕ Створити", callback_data="cp:add")])
        await update.message.reply_text(
            "Не знайдено. Введіть інший запит:",
            reply_markup=InlineKeyboardMarkup(kb) if kb else None,
        )
        return COUNTERPARTY_RESULTS
    keyboard = [
        [InlineKeyboardButton(f"{r['name']} ({r['edrpou']})", callback_data=f"cp:{r['id']}")]
        for r in rows
    ]
    if await _is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("➕ Створити", callback_data="cp:add")])
    await update.message.reply_text(
        "Оберіть контрагента:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COUNTERPARTY_RESULTS


async def counterparty_results_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "cp:add":
        await query.message.reply_text(
            "Введіть назву контрагента:", reply_markup=ReplyKeyboardRemove()
        )
        return COUNTERPARTY_CREATE_NAME
    if data.startswith("cp:"):
        cid = int(data.split(":")[1])
        context.user_data["counterparty_id"] = cid
        return await show_counterparty(query.message, context, cid)
    return COUNTERPARTY_RESULTS


async def show_counterparty(msg, context: ContextTypes.DEFAULT_TYPE, cid: int) -> int:
    row = await get_counterparty(cid)
    if not row:
        if msg.from_user and msg.from_user.id == context.bot.id:
            await msg.edit_text("Не знайдено.")
        else:
            await msg.reply_text("Не знайдено.")
        return COUNTERPARTY_RESULTS
    text = (
        f"<b>{row['name']}</b>\n"
        f"ЄДРПОУ: {row['edrpou']}\n"
        f"Директор: {row.get('director','')}\n"
        f"Адреса: {row.get('legal_address','')}\n"
        f"Телефон: {row.get('phone','')}\n"
        f"Email: {row.get('email','')}\n"
        f"Примітка: {row.get('note','')}"
    )
    kb = [[InlineKeyboardButton("✅ Обрати", callback_data="select")]]
    if await _is_admin(msg.chat_id if msg.chat_id else msg.from_user.id):
        kb.append([InlineKeyboardButton("✏️ Редагувати", callback_data="edit")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
    if msg.from_user and msg.from_user.id == context.bot.id:
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return COUNTERPARTY_VIEW


async def counterparty_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "select":
        await query.message.edit_text(
            "Введіть ID ділянок через кому:", reply_markup=ReplyKeyboardRemove()
        )
        return LAND_PLOTS
    if data == "edit":
        kb = [
            [InlineKeyboardButton("Назва", callback_data="field:name")],
            [InlineKeyboardButton("ЄДРПОУ", callback_data="field:edrpou")],
            [InlineKeyboardButton("Телефон", callback_data="field:phone")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")],
        ]
        await query.message.edit_text(
            "Оберіть поле для редагування:", reply_markup=InlineKeyboardMarkup(kb)
        )
        return COUNTERPARTY_EDIT_FIELD
    if data == "back":
        search = context.user_data.get("cp_search", "")
        rows = await search_counterparties(search)
        keyboard = [
            [InlineKeyboardButton(f"{r['name']} ({r['edrpou']})", callback_data=f"cp:{r['id']}")]
            for r in rows
        ]
        if await _is_admin(query.from_user.id):
            keyboard.append([InlineKeyboardButton("➕ Створити", callback_data="cp:add")])
        await query.message.edit_text(
            "Оберіть контрагента:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return COUNTERPARTY_RESULTS
    return COUNTERPARTY_VIEW


async def edit_field_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back":
        cid = context.user_data.get("counterparty_id")
        return await show_counterparty(query.message, context, cid)
    if data.startswith("field:"):
        field = data.split(":")[1]
        context.user_data["edit_field"] = field
        await query.message.reply_text(
            "Введіть нове значення:", reply_markup=ReplyKeyboardRemove()
        )
        return COUNTERPARTY_EDIT_VALUE
    return COUNTERPARTY_EDIT_FIELD


async def edit_value_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("edit_field")
    cid = context.user_data.get("counterparty_id")
    value = update.message.text.strip()
    await update_counterparty(cid, {field: value})
    await update.message.reply_text("Збережено.")
    return await show_counterparty(update.message, context, cid)


async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cp_name"] = update.message.text.strip()
    await update.message.reply_text("Введіть ЄДРПОУ (8 цифр):")
    return COUNTERPARTY_CREATE_EDRPOU


async def create_edrpou(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cp_edrpou"] = update.message.text.strip()
    await update.message.reply_text("Введіть телефон:")
    return COUNTERPARTY_CREATE_PHONE


async def create_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cp_phone"] = update.message.text.strip()
    cid = await add_counterparty(
        {
            "name": context.user_data.get("cp_name"),
            "edrpou": context.user_data.get("cp_edrpou"),
            "phone": context.user_data.get("cp_phone"),
        }
    )
    context.user_data["counterparty_id"] = cid
    await update.message.reply_text(
        "Контрагента створено. Введіть ID ділянок через кому:"
    )
    return LAND_PLOTS


async def land_plots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    ids: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    context.user_data["plots"] = ids
    cp = await get_counterparty(context.user_data["counterparty_id"])
    type_txt = (
        "Передача" if context.user_data["sublease_type"] == "transfer" else "Отримання"
    )
    plots_str = ", ".join(map(str, ids))
    summary = (
        f"🙋 Контрагент: {cp['name']} ({cp['edrpou']}, {cp.get('phone','')})\n"
        f"🔁 Тип: {type_txt}\n"
        f"📦 Ділянки: {plots_str}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM


async def confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "confirm":
        cid = context.user_data["counterparty_id"]
        sub_type = context.user_data["sublease_type"]
        for pid in context.user_data.get("plots", []):
            data = {
                "land_plot_id": pid,
                "counterparty_id": cid,
                "date_from": datetime.utcnow().date(),
            }
            if sub_type == "transfer":
                data["from_company_id"] = None
            else:
                data["to_company_id"] = None
            await add_sublease(data)
        await query.message.edit_text("Суборенду додано.")
        return ConversationHandler.END
    await query.message.edit_text("Скасовано.")
    return ConversationHandler.END


sublease_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Суборенда$"), start)],
    states={
        CHOOSE_TYPE: [CallbackQueryHandler(type_cb)],
        COUNTERPARTY_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, counterparty_search)],
        COUNTERPARTY_RESULTS: [
            CallbackQueryHandler(counterparty_results_cb),
            MessageHandler(filters.TEXT & ~filters.COMMAND, counterparty_search),
        ],
        COUNTERPARTY_VIEW: [CallbackQueryHandler(counterparty_view_cb)],
        COUNTERPARTY_CREATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
        COUNTERPARTY_CREATE_EDRPOU: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_edrpou)],
        COUNTERPARTY_CREATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_phone)],
        COUNTERPARTY_EDIT_FIELD: [CallbackQueryHandler(edit_field_cb)],
        COUNTERPARTY_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_cb)],
        LAND_PLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_plots)],
        CONFIRM: [CallbackQueryHandler(confirm_cb)],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), lambda u, c: ConversationHandler.END)],
)

