from db import get_company
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, MessageHandler, filters
(
    OPF_SELECT, BASE_NAME, NAME_CONFIRM, FULL_NAME_MANUAL, SHORT_NAME_MANUAL,
    ADD_EDRPOU, ADD_BANK, ADD_TAX_GROUP, ADD_VAT, ADD_VAT_IPN,
    ADD_ADDRESS_LEGAL, ADD_ADDRESS_POSTAL, ADD_DIRECTOR, CONFIRM
) = range(14)

CANCEL_BTN = "❌ Скасувати"

def get_company_names(opf, base):
    opf = opf.upper()
    base = base.strip()
    if opf == "ТОВ":
        return (
            f"ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ «{base.upper()}»",
            f"ТОВ «{base}»"
        )
    elif opf == "ФГ":
        return (
            f"ФЕРМЕРСЬКЕ ГОСПОДАРСТВО «{base.upper()}»",
            f"ФГ «{base}»"
        )
    elif opf == "ФОП":
        return (
            f"ФІЗИЧНА ОСОБА-ПІДПРИЄМЕЦЬ {base.upper()}",
            f"ФОП {base}"
        )
    elif opf == "ПП":
        return (
            f"ПРИВАТНЕ ПІДПРИЄМСТВО «{base.upper()}»",
            f"ПП «{base}»"
        )
    return (base, base)

async def admin_tov_add_start(update, context):
    kb = ReplyKeyboardMarkup([["ТОВ", "ФГ"], ["ФОП", "ПП"], [CANCEL_BTN]], resize_keyboard=True)
    await update.message.reply_text(
        "Оберіть <b>організаційно-правову форму (ОПФ)</b> компанії:",
        parse_mode="HTML",
        reply_markup=kb
    )
    return OPF_SELECT

async def admin_tov_add_opf(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov'] = {'opf': update.message.text.strip().upper()}
    await update.message.reply_text(
        "Введіть базову назву компанії (наприклад, «Зоря», або ПІБ для ФОП):",
        reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True)
    )
    return BASE_NAME

async def admin_tov_add_base_name(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    opf = context.user_data['new_tov']['opf']
    base = update.message.text.strip()
    full_name, short_name = get_company_names(opf, base)
    context.user_data['new_tov']['name'] = base
    context.user_data['new_tov']['full_name'] = full_name
    context.user_data['new_tov']['short_name'] = short_name
    kb = ReplyKeyboardMarkup([["✅ Залишити", "✏️ Змінити"], [CANCEL_BTN]], resize_keyboard=True)
    await update.message.reply_text(
        f"<b>Повна назва:</b> <code>{full_name}</code>\n"
        f"<b>Скорочена назва:</b> <code>{short_name}</code>\n\n"
        f"Бажаєте залишити як є чи ввести вручну?",
        parse_mode="HTML",
        reply_markup=kb
    )
    return NAME_CONFIRM

async def admin_tov_add_name_confirm(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    if update.message.text == "✏️ Змінити":
        await update.message.reply_text("Введіть <b>повну назву компанії</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
        return FULL_NAME_MANUAL
    else:
        await update.message.reply_text("Введіть <b>ЄДРПОУ</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
        return ADD_EDRPOU

async def admin_tov_add_full_name_manual(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['full_name'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>скорочену назву компанії</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
    return SHORT_NAME_MANUAL

async def admin_tov_add_short_name_manual(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['short_name'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>ЄДРПОУ</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
    return ADD_EDRPOU

async def admin_tov_add_edrpou(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['edrpou'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>р/р (IBAN)</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
    return ADD_BANK

async def admin_tov_add_bank(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['bank_account'] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["3 група", "4 група"], ["Загальна система"], [CANCEL_BTN]], resize_keyboard=True)
    await update.message.reply_text("Оберіть <b>групу оподаткування</b>:", parse_mode="HTML", reply_markup=kb)
    return ADD_TAX_GROUP

async def admin_tov_add_tax_group(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['tax_group'] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["Так", "Ні"], [CANCEL_BTN]], resize_keyboard=True)
    await update.message.reply_text("Чи є компанія платником ПДВ?", reply_markup=kb)
    return ADD_VAT

async def admin_tov_add_vat(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    answer = update.message.text.strip()
    context.user_data['new_tov']['is_vat_payer'] = (answer == "Так")
    if answer == "Так":
        await update.message.reply_text("Введіть <b>ІПН платника ПДВ</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
        return ADD_VAT_IPN
    else:
        context.user_data['new_tov']['vat_ipn'] = None
        await update.message.reply_text("Введіть <b>юридичну адресу</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
        return ADD_ADDRESS_LEGAL

async def admin_tov_add_vat_ipn(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['vat_ipn'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>юридичну адресу</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
    return ADD_ADDRESS_LEGAL

async def admin_tov_add_address_legal(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['address_legal'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>поштову адресу</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
    return ADD_ADDRESS_POSTAL

async def admin_tov_add_address_postal(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['address_postal'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>ПІБ директора</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True))
    return ADD_DIRECTOR

async def admin_tov_add_director(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    context.user_data['new_tov']['director'] = update.message.text.strip()
    tov = context.user_data['new_tov']
    vat_payer = "Так" if tov['is_vat_payer'] else "Ні"
    text = (
        f"<b>Перевірте дані:</b>\n"
        f"ОПФ: <code>{tov['opf']}</code>\n"
        f"Повна назва: <code>{tov['full_name']}</code>\n"
        f"Скорочена назва: <code>{tov['short_name']}</code>\n"
        f"Базова назва: <code>{tov['name']}</code>\n"
        f"ЄДРПОУ: <code>{tov['edrpou']}</code>\n"
        f"р/р: <code>{tov['bank_account']}</code>\n"
        f"Група оподаткування: <code>{tov['tax_group']}</code>\n"
        f"Платник ПДВ: <code>{vat_payer}</code>\n"
        f"ІПН платника ПДВ: <code>{tov.get('vat_ipn', '')}</code>\n"
        f"Юридична адреса: <code>{tov['address_legal']}</code>\n"
        f"Поштова адреса: <code>{tov['address_postal']}</code>\n"
        f"Директор: <code>{tov['director']}</code>\n\n"
        "Підтвердити збереження?"
    )
    kb = ReplyKeyboardMarkup([["✅ Так", "↩️ Адмінпанель"], [CANCEL_BTN]], resize_keyboard=True)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    return CONFIRM

async def admin_tov_add_confirm(update, context):
    if update.message.text == CANCEL_BTN:
        return await admin_tov_add_cancel(update, context)
    if update.message.text == "✅ Так":
        tov = context.user_data['new_tov']
        from db import add_company  # імпорт функції для додавання
        await add_company(tov)
        await update.message.reply_text("✅ Нове ТОВ успішно додано!", reply_markup=None)
    else:
        await update.message.reply_text("Операцію скасовано.", reply_markup=None)
    context.user_data.pop('new_tov', None)
    from keyboards.menu import admin_tov_menu
    await update.message.reply_text("🏢 Менеджмент ТОВ-орендарів:", reply_markup=admin_tov_menu)
    return ConversationHandler.END

async def admin_tov_add_cancel(update, context):
    context.user_data.pop('new_tov', None)
    from keyboards.menu import admin_tov_menu
    await update.message.reply_text("Додавання скасовано.", reply_markup=admin_tov_menu)
    return ConversationHandler.END

admin_tov_add_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати ТОВ$"), admin_tov_add_start)],
    states={
        OPF_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_opf)],
        BASE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_base_name)],
        NAME_CONFIRM: [MessageHandler(filters.Regex("^(✅ Залишити|✏️ Змінити)$"), admin_tov_add_name_confirm)],
        FULL_NAME_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_full_name_manual)],
        SHORT_NAME_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_short_name_manual)],
        ADD_EDRPOU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_edrpou)],
        ADD_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_bank)],
        ADD_TAX_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_tax_group)],
        ADD_VAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_vat)],
        ADD_VAT_IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_vat_ipn)],
        ADD_ADDRESS_LEGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_address_legal)],
        ADD_ADDRESS_POSTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_address_postal)],
        ADD_DIRECTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_director)],
        CONFIRM: [MessageHandler(filters.Regex("^(✅ Так|↩️ Адмінпанель|❌ Скасувати)$"), admin_tov_add_confirm)],
    },
    fallbacks=[
        MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), admin_tov_add_cancel)
    ]
)
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
        f"<b>ІПН платника ПДВ:</b> <code>{company.get('vat_ipn', '') or '—'}</code>\n"
        f"<b>Юридична адреса:</b> <code>{company['address_legal']}</code>\n"
        f"<b>Поштова адреса:</b> <code>{company['address_postal']}</code>\n"
        f"<b>Директор:</b> <code>{company['director']}</code>\n"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"company_edit:{company_id}")],
        [InlineKeyboardButton("↩️ До списку ТОВ", callback_data="company_list")],
        [InlineKeyboardButton("↩️ Адмінпанель", callback_data="admin_panel")]
    ]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
