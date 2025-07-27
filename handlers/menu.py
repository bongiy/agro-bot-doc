from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from keyboards.menu import (
    main_menu, main_menu_admin,
    payers_menu, lands_menu, fields_menu, contracts_menu,
    payments_menu, reports_menu, search_menu, admin_panel_menu, admin_tov_menu
)
from db import (
    get_companies, get_company,
    get_user_by_tg_id, add_user, get_users, update_user, log_admin_action
)


def admin_only(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        user = await get_user_by_tg_id(user_id)
        if not user or user['role'] != 'admin' or not user['is_active']:
            msg = getattr(update, 'message', None)
            if msg:
                await msg.reply_text('⛔ У вас немає прав для цієї дії.')
            else:
                await update.callback_query.answer('⛔ У вас немає прав для цієї дії.', show_alert=True)
            return
        return await handler(update, context, *args, **kwargs)
    return wrapper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    username = update.effective_user.username
    user = await get_user_by_tg_id(tg_id)
    if not user:
        await add_user(tg_id, username=username)
        user_role = "user"
    else:
        user_role = user["role"]
    await update.message.reply_text(
        "Вітаємо! Головне меню:",
        reply_markup=main_menu_admin if user_role == "admin" else main_menu
    )

async def to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_by_tg_id(update.effective_user.id)
    role = user["role"] if user else "user"
    await update.message.reply_text(
        "Головне меню:",
        reply_markup=main_menu_admin if role == "admin" else main_menu
    )

async def payers_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Пайовики»", reply_markup=payers_menu)

async def lands_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Ділянки»", reply_markup=lands_menu)

async def fields_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Поля»", reply_markup=fields_menu)

async def contracts_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Договори»", reply_markup=contracts_menu)

async def payments_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Виплати»", reply_markup=payments_menu)

async def reports_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Звіти»", reply_markup=reports_menu)

async def search_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню «Пошук»", reply_markup=search_menu)

# --- АДМІНПАНЕЛЬ ---

@admin_only
async def admin_panel_handler(update, context):

    text = (
        "🛡️ <b>Адмінпанель</b>:\n\n"
        "Оберіть розділ для адміністрування:"
    )

    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=admin_panel_menu)  # тут може бути ReplyKeyboardMarkup
    else:
        # ТУТ обовʼязково має бути InlineKeyboardMarkup!
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([])
        )


@admin_only
async def admin_tov_handler(update, context):
    msg = getattr(update, 'message', None)
    text = "🏢 Менеджмент ТОВ-орендарів:\n\nОберіть дію:"
    reply_markup = admin_tov_menu
    if msg:
        await msg.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# --- Список ТОВ (кнопка) ---
@admin_only
async def admin_tov_list_handler(update, context):
    companies = await get_companies()
    text = "<b>Список ТОВ-орендарів:</b>\nОберіть компанію для перегляду картки."
    if not companies:
        text = "Немає жодного ТОВ-орендаря."
    keyboard = [
        [InlineKeyboardButton(
            f"{c['short_name'] or c['full_name']}", callback_data=f"company_card:{c['id']}")]
        for c in companies
    ] if companies else []
    inline_kb = InlineKeyboardMarkup(keyboard)
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text(
            text, reply_markup=inline_kb, parse_mode="HTML"
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=inline_kb, parse_mode="HTML"
        )

# --- Картка ТОВ (CallbackQuery) ---
@admin_only
async def admin_company_card_callback(update, context):
    query = update.callback_query
    company_id = int(query.data.split(":")[1])
    company = await get_company(company_id)
    if not company:
        await query.answer("ТОВ не знайдено!", show_alert=True)
        return
    text = (
        f"<b>Картка ТОВ-орендаря</b>\n"
        f"<b>ОПФ:</b> <code>{company['opf']}</code>\n"
        f"<b>Повна назва:</b> <code>{company['full_name']}</code>\n"
        f"<b>Скорочена назва:</b> <code>{company['short_name']}</code>\n"
        f"<b>ЄДРПОУ:</b> <code>{company['edrpou']}</code>\n"
        f"<b>IBAN:</b> <code>{company['bank_account']}</code>\n"
        f"<b>Група оподаткування:</b> <code>{company['tax_group']}</code>\n"
        f"<b>ПДВ:</b> <code>{'так' if company['is_vat_payer'] else 'ні'}</code>\n"
        f"<b>ІПН платника ПДВ:</b> <code>{company['vat_ipn'] or '—'}</code>\n"
        f"<b>Юридична адреса:</b> <code>{company['address_legal']}</code>\n"
        f"<b>Поштова адреса:</b> <code>{company['address_postal']}</code>\n"
        f"<b>Директор:</b> <code>{company['director']}</code>\n"
    )
    keyboard = [
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"company_edit:{company_id}")],
        [InlineKeyboardButton("↩️ До списку ТОВ", callback_data="company_list")],
        [InlineKeyboardButton("↩️ Адмінпанель", callback_data="admin_panel")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --- Stub-функції для інших розділів адмінки ---

@admin_only
async def admin_templates_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Менеджмент шаблонів договорів — в розробці.")
    else:
        await update.callback_query.edit_message_text("Менеджмент шаблонів договорів — в розробці.", reply_markup=InlineKeyboardMarkup([]))

@admin_only
async def admin_users_handler(update, context):
    keyboard = [
        [InlineKeyboardButton("\U0001F4C4 Список користувачів", callback_data="user_list")],
        [InlineKeyboardButton("\u2795 Додати користувача", callback_data="user_add")],
        [InlineKeyboardButton("\U0001F501 Змінити роль", callback_data="user_role")],
        [InlineKeyboardButton("\U0001F6AB Блокування", callback_data="user_block")],
        [InlineKeyboardButton("↩️ Адмінпанель", callback_data="admin_panel")]
    ]
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text(
            "Менеджмент користувачів:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.edit_message_text(
            "Менеджмент користувачів:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

@admin_only
async def admin_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    users = await get_users()
    lines = [
        f"<code>{u['telegram_id']}</code> | {u['role']} | "
        f"{'активний' if u['is_active'] else 'заблокований'}" for u in users
    ]
    text = '<b>Список користувачів</b>:\n' + ("\n".join(lines) if lines else "Користувачів не знайдено.")
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="admin_users")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


@admin_only
async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "Введіть Telegram ID користувача:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="admin_users")]])
    )
    return ADD_USER_ID


@admin_only
async def add_user_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tg_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введіть числовий ID:")
        return ADD_USER_ID
    user = await get_user_by_tg_id(tg_id)
    if user:
        await update.message.reply_text("Користувач вже існує.")
    else:
        await add_user(tg_id)
        await log_admin_action(update.effective_user.id, f"add_user {tg_id}")
        await update.message.reply_text("Користувача додано.")
    await update.message.reply_text(
        "Менеджмент користувачів:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="admin_users")]])
    )
    return ConversationHandler.END


@admin_only
async def change_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "Введіть Telegram ID користувача:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="admin_users")]])
    )
    return CHANGE_ROLE_ID


@admin_only
async def change_role_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tg_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введіть числовий ID:")
        return CHANGE_ROLE_ID
    user = await get_user_by_tg_id(tg_id)
    if not user:
        await update.message.reply_text("Користувача не знайдено.")
    else:
        new_role = "user" if user["role"] == "admin" else "admin"
        await update_user(tg_id, {"role": new_role})
        await log_admin_action(update.effective_user.id, f"toggle_role {tg_id}")
        await update.message.reply_text(f"Роль змінено на {new_role}.")
    await update.message.reply_text(
        "Менеджмент користувачів:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="admin_users")]])
    )
    return ConversationHandler.END


@admin_only
async def block_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "Введіть Telegram ID користувача:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="admin_users")]])
    )
    return BLOCK_USER_ID


@admin_only
async def block_user_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tg_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введіть числовий ID:")
        return BLOCK_USER_ID
    user = await get_user_by_tg_id(tg_id)
    if not user:
        await update.message.reply_text("Користувача не знайдено.")
    else:
        new_status = not user["is_active"]
        await update_user(tg_id, {"is_active": new_status})
        action = "unblock" if new_status else "block"
        await log_admin_action(update.effective_user.id, f"{action} {tg_id}")
        text = "Користувача розблоковано." if new_status else "Користувача заблоковано."
        await update.message.reply_text(text)
    await update.message.reply_text(
        "Менеджмент користувачів:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="admin_users")]])
    )
    return ConversationHandler.END


@admin_only
async def admin_delete_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Видалення об’єктів — в розробці.")
    else:
        await update.callback_query.edit_message_text("Видалення об’єктів — в розробці.", reply_markup=InlineKeyboardMarkup([]))

@admin_only
async def admin_tov_edit_handler(update, context):
    companies = await get_companies()
    text = "<b>Оберіть ТОВ для редагування:</b>"
    if not companies:
        text = "Немає жодного ТОВ-орендаря."
    keyboard = [
        [InlineKeyboardButton(
            f"{c['short_name'] or c['full_name']}", callback_data=f"company_edit:{c['id']}"
        )]
        for c in companies
    ] if companies else []
    inline_kb = InlineKeyboardMarkup(keyboard)
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text(text, reply_markup=inline_kb, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=inline_kb, parse_mode="HTML")

@admin_only
async def admin_tov_delete_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Видалення ТОВ — в розробці.")
    else:
        await update.callback_query.edit_message_text("Видалення ТОВ — в розробці.", reply_markup=InlineKeyboardMarkup([]))

@admin_only
async def to_admin_panel(update, context):
    from keyboards.menu import admin_panel_menu
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("🛡️ Адмінпанель:", reply_markup=admin_panel_menu)
    else:
        await update.callback_query.edit_message_text("🛡️ Адмінпанель:", reply_markup=admin_panel_menu)


# --- Команди адміністрування користувачів ---

@admin_only
async def cmd_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = await get_users()
    lines = [f"{u['telegram_id']} | {u['role']} | {'активний' if u['is_active'] else 'заблокований'}" for u in users]
    text = "\n".join(lines) if lines else "Користувачів не знайдено."
    await update.message.reply_text(text)

@admin_only
async def cmd_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Вкажіть Telegram ID користувача.')
        return
    tg_id = int(context.args[0])
    user = await get_user_by_tg_id(tg_id)
    if user:
        await update.message.reply_text('Користувач вже існує.')
        return
    await add_user(tg_id)
    await log_admin_action(update.effective_user.id, f"add_user {tg_id}")
    await update.message.reply_text('Користувача додано.')

@admin_only
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Вкажіть Telegram ID.')
        return
    tg_id = int(context.args[0])
    await update_user(tg_id, {'role': 'admin'})
    await log_admin_action(update.effective_user.id, f"promote {tg_id}")
    await update.message.reply_text('Роль змінено на admin.')

@admin_only
async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Вкажіть Telegram ID.')
        return
    tg_id = int(context.args[0])
    await update_user(tg_id, {'role': 'user'})
    await log_admin_action(update.effective_user.id, f"demote {tg_id}")
    await update.message.reply_text('Роль змінено на user.')

@admin_only
async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Вкажіть Telegram ID.')
        return
    tg_id = int(context.args[0])
    await update_user(tg_id, {'is_active': False})
    await log_admin_action(update.effective_user.id, f"block {tg_id}")
    await update.message.reply_text('Користувача заблоковано.')

@admin_only
async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Вкажіть Telegram ID.')
        return
    tg_id = int(context.args[0])
    await update_user(tg_id, {'is_active': True})
    await log_admin_action(update.effective_user.id, f"unblock {tg_id}")
    await update.message.reply_text('Користувача розблоковано.')


# --- Conversation handlers for user management ---
add_user_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_user_start, pattern=r"^user_add$")],
    states={
        ADD_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_finish)],
    },
    fallbacks=[CallbackQueryHandler(admin_users_handler, pattern=r"^admin_users$")]
)

change_role_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(change_role_start, pattern=r"^user_role$")],
    states={
        CHANGE_ROLE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_role_finish)],
    },
    fallbacks=[CallbackQueryHandler(admin_users_handler, pattern=r"^admin_users$")]
)

block_user_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(block_user_start, pattern=r"^user_block$")],
    states={
        BLOCK_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_finish)],
    },
    fallbacks=[CallbackQueryHandler(admin_users_handler, pattern=r"^admin_users$")]
)
