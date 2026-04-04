import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ConversationHandler
)
from handlers.menu import (
    start,
    to_main_menu,
    refresh_menu,
    payers_menu_handler,
    lands_menu_handler,
    fields_menu_handler,
    contracts_menu_handler,
    payments_menu_handler,
    search_menu_handler,
    ezem_menu_handler,
    warehouse_menu_handler,
    logistics_menu_handler,
    reports_menu_handler,
    logistics_add_trip_handler,
    logistics_journal_handler,
    logistics_vehicles_handler,
    logistics_counterparties_handler,
    logistics_ttn_handler,
    doc_recognition_handler,
    heirs_menu_handler,
    ezem_events_handler,
    crm_menu_handler,
    crm_potential_handler,
    crm_current_handler,
    crm_planning_handler,
    crm_events_handler,
    crm_reminders_handler,
    inbox_menu_handler,
    payroll_menu_handler,
    admin_panel_handler,
    admin_tov_handler,
    admin_templates_handler,
    admin_users_handler,
    admin_delete_handler,
    admin_access_handler,
    admin_tov_list_handler,
    admin_tov_edit_handler,
    admin_tov_delete_handler,
    to_admin_panel,
    admin_company_card_callback,
    admin_user_list,
    add_user_conv,
    change_role_conv,
    block_user_conv,
    change_name_conv,
    company_delete_prompt,
    company_delete_confirm,
)
from handlers.menu import (
    cmd_list_users, cmd_add_user, cmd_promote, cmd_demote, cmd_block, cmd_unblock
)
from dialogs.payer import (
    add_payer_conv, show_payers, payer_card, delete_payer, delete_payer_prompt,
    to_menu
)
from dialogs.heir import add_heir_conv
from dialogs.edit_payer import edit_payer_conv
from dialogs.search import search_payer_conv, search_land_conv, search_contract_conv
from dialogs.field import add_field_conv, show_fields, delete_field, delete_field_prompt, to_fields_list, field_card, edit_field
from dialogs.land import (
    add_land_conv,
    show_lands,
    land_card,
    delete_land,
    delete_land_prompt,
    to_lands_list,
    start_land_for_payer,
)
from dialogs.contract import (
    add_contract_conv,
    show_contracts,
    agreement_card,
    to_contracts,
    contract_docs,
    delete_contract_prompt,
    delete_contract,
    agreement_delete_prompt,
    agreement_delete_confirm,
    generate_contract_docx_cb,
    edit_contract_conv,
    change_status_conv,
    payment_summary_cb,
    payment_history_cb,
)
from dialogs.payment import (
    add_payment_conv,
    global_add_payment_conv,
    select_payer_cb,
    select_contract_cb,
    show_payments,
    list_inheritance_debts,
    payment_report_conv,
)
from dialogs.rent_summary import rent_summary_conv
from dialogs.land_report import land_report_conv
from dialogs.land_overview import land_overview_conv
from dialogs.fields_report import fields_report_conv
from dialogs.contract_overview import contract_overview_conv
from dialogs.company_report import company_report_conv
from dialogs.edit_field import edit_field_conv
from dialogs.edit_land import edit_land_conv
from dialogs.edit_land_owner import edit_land_owner_conv
from dialogs.add_docs_fsm import add_docs_conv, send_pdf, delete_pdf, confirm_delete_doc, cancel_delete_doc  # тільки FTP!
from dialogs.post_creation import skip_add_docs
from db import database, ensure_admin
from db import ensure_payroll_defaults
from dialogs.payroll import (
    payroll_employees_handler,
    payroll_worklog_handler,
    payroll_accruals_handler,
    payroll_rates_handler,
    payroll_booking_handler,
    payroll_tasks_handler,
    payroll_personal_handler,
    payroll_arrived_handler,
    payroll_finished_handler,
    payroll_location_handler,
    payroll_my_month_handler,
    payroll_add_employee_cmd,
    payroll_recalc_month_cmd,
    payroll_add_log_cmd,
)

from dialogs.admin_tov import admin_tov_add_conv
from dialogs.edit_company import edit_company_conv
from dialogs.potential_payer import (
    add_potential_conv,
    list_potential,
    potential_callbacks,
    filter_potential_conv,
)
from dialogs.agreement_template import (
    add_template_conv, replace_template_conv,
    template_card_cb, template_toggle_cb, template_delete_cb,
    template_list_cb, show_templates_cb,
    template_vars_cb, template_vars_categories_cb
)

from crm.events import add_event_conv
from crm.events_fsm_rewrite_final import view_event_conv
from crm.events_integration import add_event_from_card_conv
from crm.event_reminders import start_reminder_tasks, stop_reminder_tasks
from crm.payer_request import add_request_conv
from crm.fsm_view_payer_requests import view_requests_conv
from crm.fsm_update_payer_request import update_request_conv
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()
application = Application.builder().token(TOKEN).build()
DEFAULT_ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "370806943").split(",") if i]
is_initialized = False

@app.on_event("startup")
async def on_startup():
    global is_initialized
    await database.connect()
    for admin_id in DEFAULT_ADMIN_IDS:
        await ensure_admin(admin_id)
    await ensure_payroll_defaults()
    if not is_initialized:
        await application.initialize()
        await application.bot.set_webhook(WEBHOOK_URL)
        start_reminder_tasks(application)
        is_initialized = True

@app.on_event("shutdown")
async def on_shutdown():
    await stop_reminder_tasks()
    await database.disconnect()

# === Основні handlers ===

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("users", cmd_list_users))
application.add_handler(CommandHandler("add_user", cmd_add_user))
application.add_handler(CommandHandler("promote", cmd_promote))
application.add_handler(CommandHandler("demote", cmd_demote))
application.add_handler(CommandHandler("block", cmd_block))
application.add_handler(CommandHandler("unblock", cmd_unblock))
application.add_handler(CommandHandler("refresh", refresh_menu))
application.add_handler(MessageHandler(filters.Regex("^◀️ Назад$"), to_main_menu))
application.add_handler(MessageHandler(filters.Regex("^🌐 e-Землевпорядник$"), ezem_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🧩 CRM$"), crm_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^📊 Звіти$"), reports_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^💼 Облік ЗП$"), payroll_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🚛 Логістика$"), logistics_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🤖 Розпізнавання документів$"), doc_recognition_handler))
application.add_handler(MessageHandler(filters.Regex("^📁 Пайовики$"), payers_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🌍 Ділянки$"), lands_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^📄 Договори$"), contracts_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🧾 Виплати$"), payments_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^📆 Події / Нагадування$"), ezem_events_handler))
application.add_handler(MessageHandler(filters.Regex("^📬 Звернення та заяви$"), inbox_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^🔍 Пошук$"), search_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^👨‍👩‍👧‍👦 Спадкоємці$"), heirs_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^⚙️ Адмін-панель$"), admin_panel_handler))
application.add_handler(MessageHandler(filters.Regex("^🧑‍🌾 Потенційні пайовики$"), crm_potential_handler))
application.add_handler(MessageHandler(filters.Regex("^👥 Поточні пайовики$"), crm_current_handler))
application.add_handler(MessageHandler(filters.Regex("^📅 Планування$"), crm_planning_handler))
application.add_handler(MessageHandler(filters.Regex("^📬 Звернення$"), inbox_menu_handler))
application.add_handler(MessageHandler(filters.Regex("^📆 Події$"), crm_events_handler))
application.add_handler(MessageHandler(filters.Regex("^🧠 Нагадування$"), crm_reminders_handler))
application.add_handler(MessageHandler(filters.Regex("^➕ Додати рейс$"), logistics_add_trip_handler))
application.add_handler(MessageHandler(filters.Regex("^📋 Журнал рейсів$"), logistics_journal_handler))
application.add_handler(MessageHandler(filters.Regex("^🛻 Техніка$"), logistics_vehicles_handler))
application.add_handler(MessageHandler(filters.Regex("^🧾 Контрагенти$"), logistics_counterparties_handler))
application.add_handler(MessageHandler(filters.Regex("^📄 Шаблони ТТН$"), logistics_ttn_handler))

# --- Payroll ---
application.add_handler(CommandHandler("payroll_add_employee", payroll_add_employee_cmd))
application.add_handler(CommandHandler("payroll_recalc_month", payroll_recalc_month_cmd))
application.add_handler(CommandHandler("payroll_add_log", payroll_add_log_cmd))
application.add_handler(MessageHandler(filters.Regex("^👤 Працівники$"), payroll_employees_handler))
application.add_handler(MessageHandler(filters.Regex("^📘 Журнал робіт$"), payroll_worklog_handler))
application.add_handler(MessageHandler(filters.Regex("^🧮 Нарахування$"), payroll_accruals_handler))
application.add_handler(MessageHandler(filters.Regex("^⚙️ Операції і ставки$"), payroll_rates_handler))
application.add_handler(MessageHandler(filters.Regex("^🪖 Бронювання / КЕФ$"), payroll_booking_handler))
application.add_handler(MessageHandler(filters.Regex("^🎯 Задачі$"), payroll_tasks_handler))
application.add_handler(MessageHandler(filters.Regex("^👨‍💼 Особистий кабінет$"), payroll_personal_handler))
application.add_handler(MessageHandler(filters.Regex("^📍 Я прибув$"), payroll_arrived_handler))
application.add_handler(MessageHandler(filters.Regex("^🏁 Завершив роботу$"), payroll_finished_handler))
application.add_handler(MessageHandler(filters.Regex("^📅 Поточний місяць$"), payroll_my_month_handler))
application.add_handler(MessageHandler(filters.LOCATION, payroll_location_handler))
application.add_handler(MessageHandler(filters.Regex("^🎯 Мої задачі$"), payroll_tasks_handler))

# --- ПАЙОВИКИ: Підключаємо діалоги до підменю пайовиків
application.add_handler(add_payer_conv)
application.add_handler(add_heir_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список пайовиків$"), show_payers))
application.add_handler(search_payer_conv)
application.add_handler(search_land_conv)
application.add_handler(search_contract_conv)
application.add_handler(edit_payer_conv)
application.add_handler(global_add_payment_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Перелік виплат$"), show_payments))
application.add_handler(MessageHandler(filters.Regex("^🔍 Борг перед спадкоємцем$"), list_inheritance_debts))
application.add_handler(payment_report_conv)
application.add_handler(rent_summary_conv)
application.add_handler(land_report_conv)
application.add_handler(land_overview_conv)
application.add_handler(fields_report_conv)
application.add_handler(contract_overview_conv)
application.add_handler(company_report_conv)

# --- Потенційні пайовики ---
application.add_handler(add_potential_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список$"), list_potential))
application.add_handler(filter_potential_conv)

# --- ДІЛЯНКИ/ПОЛЯ ---
application.add_handler(add_field_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список полів$"), show_fields))
# --- Планування та події ---
application.add_handler(add_event_conv)
application.add_handler(add_event_from_card_conv)
application.add_handler(view_event_conv)
application.add_handler(add_request_conv)
application.add_handler(view_requests_conv)
application.add_handler(update_request_conv)

application.add_handler(add_land_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список ділянок$"), show_lands))
application.add_handler(add_contract_conv)
application.add_handler(MessageHandler(filters.Regex("^📋 Список договорів$"), show_contracts))

application.add_handler(CallbackQueryHandler(field_card, pattern=r"^field_card:"))
application.add_handler(CallbackQueryHandler(delete_field_prompt, pattern=r"^delete_field:\d+$"))
application.add_handler(CallbackQueryHandler(delete_field, pattern=r"^confirm_delete_field:\d+$"))
application.add_handler(CallbackQueryHandler(to_fields_list, pattern=r"^to_fields_list$"))

application.add_handler(CallbackQueryHandler(land_card, pattern=r"^land_card:"))
application.add_handler(CallbackQueryHandler(delete_land_prompt, pattern=r"^delete_land:\d+$"))
application.add_handler(CallbackQueryHandler(delete_land, pattern=r"^confirm_delete_land:\d+$"))
application.add_handler(CallbackQueryHandler(to_lands_list, pattern=r"^to_lands_list$"))
application.add_handler(CallbackQueryHandler(start_land_for_payer, pattern=r"^start_land:\d+$"))

application.add_handler(edit_field_conv)
application.add_handler(edit_land_conv)
application.add_handler(edit_land_owner_conv)
application.add_handler(edit_company_conv)

# --- Документи через FTP ---
application.add_handler(add_docs_conv)
application.add_handler(CallbackQueryHandler(send_pdf, pattern=r"^send_pdf:\d+$"))
application.add_handler(CallbackQueryHandler(delete_pdf, pattern=r"^delete_pdf_db:\d+$"))
application.add_handler(CallbackQueryHandler(confirm_delete_doc, pattern=r"^confirm_delete_doc:\d+$"))
application.add_handler(CallbackQueryHandler(cancel_delete_doc, pattern=r"^cancel_delete_doc:\d+$"))
application.add_handler(CallbackQueryHandler(skip_add_docs, pattern=r"^skip_docs:\w+:\d+$"))

# CallbackQueryHandler-и — як є, доки не переведені на нову систему:
application.add_handler(CallbackQueryHandler(payer_card, pattern=r"^payer_card:"))
application.add_handler(CallbackQueryHandler(delete_payer_prompt, pattern=r"^delete_payer:\d+$"))
application.add_handler(CallbackQueryHandler(delete_payer, pattern=r"^confirm_delete_payer:\d+$"))
application.add_handler(CallbackQueryHandler(to_menu, pattern=r"^to_menu$"))
application.add_handler(CallbackQueryHandler(agreement_card, pattern=r"^(contract_card|agreement_card):\d+$"))
application.add_handler(edit_contract_conv)
application.add_handler(change_status_conv)
application.add_handler(add_payment_conv)
application.add_handler(CallbackQueryHandler(select_payer_cb, pattern=r"^pay_select:\d+$"))
application.add_handler(CallbackQueryHandler(select_contract_cb, pattern=r"^pay_contract:\d+$"))
application.add_handler(CallbackQueryHandler(payment_summary_cb, pattern=r"^payment_summary:\d+$"))
application.add_handler(CallbackQueryHandler(payment_history_cb, pattern=r"^payment_history:\d+$"))
application.add_handler(CallbackQueryHandler(generate_contract_docx_cb, pattern=r"^generate_contract_docx:\d+$"))
application.add_handler(CallbackQueryHandler(contract_docs, pattern=r"^contract_docs:\d+$"))
application.add_handler(CallbackQueryHandler(delete_contract_prompt, pattern=r"^delete_contract:\d+$"))
application.add_handler(CallbackQueryHandler(delete_contract, pattern=r"^confirm_delete_contract:\d+$"))
application.add_handler(CallbackQueryHandler(agreement_delete_prompt, pattern=r"^agreement_delete:\d+$"))
application.add_handler(CallbackQueryHandler(agreement_delete_confirm, pattern=r"^agreement_delete_confirm$"))
application.add_handler(CallbackQueryHandler(to_contracts, pattern=r"^to_contracts$"))
for cb in potential_callbacks:
    application.add_handler(cb)

# fallback: обробляємо всі невідомі команди поверненням у головне меню
application.add_handler(MessageHandler(filters.COMMAND, to_main_menu))

# --- АДМІНКА ---
application.add_handler(admin_tov_add_conv)
application.add_handler(add_template_conv)
application.add_handler(replace_template_conv)
application.add_handler(template_card_cb)
application.add_handler(template_toggle_cb)
application.add_handler(template_delete_cb)
application.add_handler(template_list_cb)
application.add_handler(template_vars_cb)
application.add_handler(template_vars_categories_cb)
application.add_handler(MessageHandler(filters.Regex("^🧾 Шаблони документів$"), admin_templates_handler))
application.add_handler(MessageHandler(filters.Regex("^📋 Список шаблонів$"), show_templates_cb))
application.add_handler(MessageHandler(filters.Regex("^👤 Менеджмент користувачів$"), admin_users_handler))
application.add_handler(MessageHandler(filters.Regex("^🗑️ Видалення об'єктів$"), admin_delete_handler))
application.add_handler(MessageHandler(filters.Regex("^🔐 Права доступу$"), admin_access_handler))
application.add_handler(MessageHandler(filters.Regex("^↩️ Головне меню$"), to_main_menu))
application.add_handler(CallbackQueryHandler(admin_user_list, pattern=r"^user_list$"))
application.add_handler(add_user_conv)
application.add_handler(change_role_conv)
application.add_handler(block_user_conv)
application.add_handler(change_name_conv)
application.add_handler(CallbackQueryHandler(admin_users_handler, pattern=r"^admin_users$"))
# --- АДМІНКА ТОВ ---
application.add_handler(MessageHandler(filters.Regex("^🏢 ТОВ-орендарі$"), admin_tov_handler))
application.add_handler(MessageHandler(filters.Regex("^📋 Список ТОВ$"), admin_tov_list_handler))
application.add_handler(MessageHandler(filters.Regex("^✏️ Редагувати ТОВ$"), admin_tov_edit_handler))
application.add_handler(MessageHandler(filters.Regex("^🗑️ Видалити ТОВ$"), admin_tov_delete_handler))
application.add_handler(MessageHandler(filters.Regex("^↩️ Адмін-панель$"), to_admin_panel))
application.add_handler(CallbackQueryHandler(admin_company_card_callback, pattern=r"^company_card:\d+$"))
application.add_handler(CallbackQueryHandler(company_delete_prompt, pattern=r"^company_delete:\d+$"))
application.add_handler(CallbackQueryHandler(company_delete_confirm, pattern=r"^company_delete_confirm:\d+$"))
application.add_handler(CallbackQueryHandler(admin_tov_list_handler, pattern=r"^company_list$"))
application.add_handler(CallbackQueryHandler(admin_panel_handler, pattern=r"^admin_panel$"))


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    global is_initialized
    if not is_initialized:
        await application.initialize()
        is_initialized = True
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
