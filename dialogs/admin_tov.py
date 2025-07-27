from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, MessageHandler, filters

(
    ADD_NAME, ADD_EDRPOU, ADD_BANK, ADD_TAX_GROUP, ADD_VAT, ADD_VAT_IPN,
    ADD_ADDRESS_LEGAL, ADD_ADDRESS_POSTAL, ADD_DIRECTOR, CONFIRM
) = range(10)

async def admin_tov_add_start(update, context):
    await update.message.reply_text("Введіть <b>назву ТОВ</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    return ADD_NAME

async def admin_tov_add_name(update, context):
    context.user_data['new_tov'] = {'name': update.message.text.strip()}
    await update.message.reply_text("Введіть <b>ЄДРПОУ</b>:", parse_mode="HTML")
    return ADD_EDRPOU

async def admin_tov_add_edrpou(update, context):
    context.user_data['new_tov']['edrpou'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>р/р (IBAN)</b>:", parse_mode="HTML")
    return ADD_BANK

async def admin_tov_add_bank(update, context):
    context.user_data['new_tov']['bank_account'] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["3 група", "4 група"], ["Загальна система"]], resize_keyboard=True)
    await update.message.reply_text("Оберіть <b>групу оподаткування</b>:", parse_mode="HTML", reply_markup=kb)
    return ADD_TAX_GROUP

async def admin_tov_add_tax_group(update, context):
    context.user_data['new_tov']['tax_group'] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["Так", "Ні"]], resize_keyboard=True)
    await update.message.reply_text("Чи є компанія платником ПДВ?", reply_markup=kb)
    return ADD_VAT

async def admin_tov_add_vat(update, context):
    answer = update.message.text.strip()
    context.user_data['new_tov']['is_vat_payer'] = (answer == "Так")
    if answer == "Так":
        await update.message.reply_text("Введіть <b>ІПН платника ПДВ</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        return ADD_VAT_IPN
    else:
        context.user_data['new_tov']['vat_ipn'] = None
        await update.message.reply_text("Введіть <b>юридичну адресу</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        return ADD_ADDRESS_LEGAL

async def admin_tov_add_vat_ipn(update, context):
    context.user_data['new_tov']['vat_ipn'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>юридичну адресу</b>:", parse_mode="HTML")
    return ADD_ADDRESS_LEGAL

async def admin_tov_add_address_legal(update, context):
    context.user_data['new_tov']['address_legal'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>поштову адресу</b>:", parse_mode="HTML")
    return ADD_ADDRESS_POSTAL

async def admin_tov_add_address_postal(update, context):
    context.user_data['new_tov']['address_postal'] = update.message.text.strip()
    await update.message.reply_text("Введіть <b>ПІБ директора</b>:", parse_mode="HTML")
    return ADD_DIRECTOR

async def admin_tov_add_director(update, context):
    context.user_data['new_tov']['director'] = update.message.text.strip()
    tov = context.user_data['new_tov']
    vat_payer = "Так" if tov['is_vat_payer'] else "Ні"
    text = (
        f"<b>Перевірте дані:</b>\n"
        f"Назва: <code>{tov['name']}</code>\n"
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
    kb = ReplyKeyboardMarkup([["✅ Так", "↩️ Адмінпанель"]], resize_keyboard=True)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    return CONFIRM

async def admin_tov_add_confirm(update, context):
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

# === Оголошення FSM ===
admin_tov_add_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Додати ТОВ$"), admin_tov_add_start)],
    states={
        0: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_name)],
        1: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_edrpou)],
        2: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_bank)],
        3: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_tax_group)],
        4: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_vat)],
        5: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_vat_ipn)],
        6: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_address_legal)],
        7: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_address_postal)],
        8: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tov_add_director)],
        9: [MessageHandler(filters.Regex("^(✅ Так|↩️ Адмінпанель)$"), admin_tov_add_confirm)]
    },
    fallbacks=[]
)
