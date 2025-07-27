from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from keyboards.menu import (
    main_menu, main_menu_admin,
    payers_menu, lands_menu, fields_menu, contracts_menu,
    payments_menu, reports_menu, search_menu, admin_panel_menu, admin_tov_menu
)
from db import get_companies, get_company

admin_ids = [370806943]  # TODO: Замініть цей список на актуальні admin_ids або імпортуйте з config

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in admin_ids
    await update.message.reply_text(
        "Вітаємо! Головне меню:",
        reply_markup=main_menu_admin if is_admin else main_menu
    )

async def to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in admin_ids
    await update.message.reply_text(
        "Головне меню:",
        reply_markup=main_menu_admin if is_admin else main_menu
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

async def admin_panel_handler(update, context):
    admin_ids = [370806943]  # <--- твій tg_id
    if update.effective_user.id not in admin_ids:
        msg = getattr(update, 'message', None)
        if msg:
            await msg.reply_text("У вас немає прав для цієї дії.")
        else:
            await update.callback_query.answer("У вас немає прав для цієї дії.", show_alert=True)
        return
    text = (
        "🛡️ <b>Адмінпанель</b>:\n\n"
        "Оберіть розділ для адміністрування:"
    )
    reply_markup = admin_panel_menu
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def admin_tov_handler(update, context):
    msg = getattr(update, 'message', None)
    text = "🏢 Менеджмент ТОВ-орендарів:\n\nОберіть дію:"
    reply_markup = admin_tov_menu
    if msg:
        await msg.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# --- Список ТОВ (кнопка) ---
async def admin_tov_list_handler(update, context):
    companies = await get_companies()
    text = "<b>Список ТОВ-орендарів:</b>\nОберіть компанію для перегляду картки."
    if not companies:
        text = "Немає жодного ТОВ-орендаря."
    keyboard = [
        [InlineKeyboardButton(
            f"{c['short_name'] or c['full_name']}", callback_data=f"company_card:{c['id']}")]
        for c in companies
    ] if companies else None

    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="HTML"
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="HTML"
        )

# --- Картка ТОВ (CallbackQuery) ---
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

async def admin_templates_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Менеджмент шаблонів договорів — в розробці.")
    else:
        await update.callback_query.edit_message_text("Менеджмент шаблонів договорів — в розробці.")

async def admin_users_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Менеджмент користувачів — в розробці.")
    else:
        await update.callback_query.edit_message_text("Менеджмент користувачів — в розробці.")

async def admin_delete_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Видалення об’єктів — в розробці.")
    else:
        await update.callback_query.edit_message_text("Видалення об’єктів — в розробці.")

async def admin_tov_edit_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Редагування ТОВ — в розробці.")
    else:
        await update.callback_query.edit_message_text("Редагування ТОВ — в розробці.")

async def admin_tov_delete_handler(update, context):
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("Видалення ТОВ — в розробці.")
    else:
        await update.callback_query.edit_message_text("Видалення ТОВ — в розробці.")

async def to_admin_panel(update, context):
    from keyboards.menu import admin_panel_menu
    msg = getattr(update, 'message', None)
    if msg:
        await msg.reply_text("🛡️ Адмінпанель:", reply_markup=admin_panel_menu)
    else:
        await update.callback_query.edit_message_text("🛡️ Адмінпанель:", reply_markup=admin_panel_menu)
