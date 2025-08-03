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
    get_counterparties,
    get_counterparty,
    add_sublease,
)

# conversation states
(
    CHOOSE_TYPE,
    COUNTERPARTY_LIST,
    COUNTERPARTY_CREATE_NAME,
    COUNTERPARTY_CREATE_EDRPOU,
    COUNTERPARTY_CREATE_PHONE,
    LAND_PLOTS,
    CONFIRM,
) = range(7)


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
    rows = await get_counterparties()
    keyboard = [
        [
            InlineKeyboardButton(
                f"{r['name']} ({r['edrpou']})", callback_data=f"cp:{r['id']}"
            )
        ]
        for r in rows[:5]
    ]
    keyboard.append([InlineKeyboardButton("➕ Створити", callback_data="cp:add")])
    await query.message.edit_text(
        "Оберіть контрагента:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COUNTERPARTY_LIST


async def counterparty_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        await query.message.reply_text(
            "Введіть ID ділянок через кому:", reply_markup=ReplyKeyboardRemove()
        )
        return LAND_PLOTS
    return COUNTERPARTY_LIST


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
    await update.message.reply_text("Контрагента створено. Введіть ID ділянок через кому:")
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
        COUNTERPARTY_LIST: [CallbackQueryHandler(counterparty_list_cb)],
        COUNTERPARTY_CREATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
        COUNTERPARTY_CREATE_EDRPOU: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_edrpou)],
        COUNTERPARTY_CREATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_phone)],
        LAND_PLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_plots)],
        CONFIRM: [CallbackQueryHandler(confirm_cb)],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), lambda u, c: ConversationHandler.END)],
)

