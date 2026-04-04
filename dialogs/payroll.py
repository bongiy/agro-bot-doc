from datetime import date, datetime
from decimal import Decimal

import sqlalchemy
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db import (
    Employee,
    EmployeeMonthSummary,
    KefRule,
    OperationsCatalog,
    BookingSettings,
    WorkLog,
    add_employee,
    add_work_log_entry,
    create_employee_invite,
    database,
    get_attendance_by_employee,
    get_employee,
    get_employee_by_tg_id,
    get_employee_invite,
    get_employees,
    get_employee_tasks,
    get_or_create_payroll_period,
    get_user_by_tg_id,
    get_work_log_entries,
    log_admin_action,
    mark_invite_used,
    update_employee,
    upsert_employee_by_telegram_id,
    upsert_attendance_arrival,
    upsert_attendance_finish,
)
from keyboards.menu import (
    payroll_menu,
    payroll_pending_menu,
    payroll_personal_menu,
    payroll_personal_menu_land_manager,
)
from utils.payroll import (
    calculate_employee_month_summary,
    calculate_kef_for_log_entry,
    calculate_salary_for_log_entry,
)


async def payroll_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_by_tg_id(update.effective_user.id)
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if user and user["role"] == "admin":
        await update.message.reply_text("💼 Облік ЗП", reply_markup=payroll_menu)
        return
    if employee and employee["registration_status"] == "approved" and employee["is_active"]:
        await update.message.reply_text("💼 Облік ЗП", reply_markup=payroll_menu)
        return
    if employee and employee["registration_status"] == "pending":
        await update.message.reply_text(
            "⏳ Ваша реєстрація очікує підтвердження адміністратора.",
            reply_markup=payroll_pending_menu,
        )
        return
    await update.message.reply_text("Доступ до модуля відкриється після підтвердження заявки адміністратором.")


async def payroll_employees_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await update.message.reply_text("⛔ Доступно лише адміністратору.")
        return
    employees = await get_employees(active_only=False)
    if not employees:
        await update.message.reply_text(
            "Працівників ще немає. Для створення використайте /payroll_add_employee ІМ'Я | role_code | telegram_id"
        )
        return
    lines = [
        (
            f"• #{e['id']} {e['full_name']} ({e['role_code']}) "
            f"{'✅' if e['is_active'] else '⛔'} [{e['registration_status']}] "
            f"tg:{e['telegram_user_id'] or '—'}"
        )
        for e in employees
    ]
    await update.message.reply_text("👤 Працівники:\n" + "\n".join(lines))


async def payroll_worklog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    period = await get_or_create_payroll_period(today.year, today.month)
    rows = await get_work_log_entries(period_id=period["id"])
    if not rows:
        await update.message.reply_text("📘 Журнал робіт порожній за поточний місяць.")
        return
    text_rows = []
    for row in rows[:30]:
        text_rows.append(
            f"{row['date']}: emp#{row['employee_id']} {row['work_type']} | КЕФ {row['kef_amount']} | ЗП {row['salary_amount']}"
        )
    await update.message.reply_text("📘 Журнал робіт (останні записи):\n" + "\n".join(text_rows))


async def payroll_accruals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    period = await get_or_create_payroll_period(today.year, today.month)
    summaries = await database.fetch_all(
        EmployeeMonthSummary.select()
        .where(EmployeeMonthSummary.c.period_id == period["id"])
        .order_by(EmployeeMonthSummary.c.employee_id)
    )
    if not summaries:
        await update.message.reply_text("🧮 Нарахування ще не сформовані. Використайте /payroll_recalc_month")
        return
    lines = []
    for s in summaries:
        lines.append(
            f"emp#{s['employee_id']}: КЕФ={s['total_kef']} бронь={s['kef_used_for_booking']} перебір={s['kef_over']} недобір={s['kef_shortage']} до виплати={s['total_to_pay']}"
        )
    await update.message.reply_text("🧮 Нарахування за місяць:\n" + "\n".join(lines))


async def payroll_rates_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await database.fetch_all(
        OperationsCatalog.select().where(OperationsCatalog.c.is_active.is_(True)).order_by(OperationsCatalog.c.role_code)
    )
    if not rows:
        await update.message.reply_text("⚙️ Операції і ставки відсутні.")
        return
    lines = [f"• [{r['role_code']}] {r['name']} = {r['rate_value']} / {r['unit_type']}" for r in rows[:40]]
    await update.message.reply_text("⚙️ Операції і ставки:\n" + "\n".join(lines))


async def payroll_reports_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await payroll_accruals_handler(update, context)


async def payroll_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = await database.fetch_one(BookingSettings.select().limit(1))
    if not settings:
        await update.message.reply_text("🪖 Налаштування бронювання не заповнені.")
        return
    await update.message.reply_text(
        "🪖 Бронювання/КЕФ:\n"
        f"Вартість: {settings['booking_month_cost']} грн\n"
        f"1 КЕФ: {settings['kef_money_value']} грн\n"
        f"Потрібно: {settings['booking_required_kef']} КЕФ"
    )


async def payroll_tasks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("🎯 Ви не прив'язані до працівника.")
        return
    if employee["registration_status"] != "approved" or not employee["is_active"]:
        await update.message.reply_text("⛔ Доступ до задач буде відкрито після підтвердження/активації.")
        return
    tasks = await get_employee_tasks(employee["id"], active_only=False)
    if not tasks:
        await update.message.reply_text("🎯 Немає задач.")
        return
    lines = [f"• {t['title']} ({t['status']}) до {t['due_date'] or '—'}" for t in tasks]
    await update.message.reply_text("🎯 Ваші задачі:\n" + "\n".join(lines))


async def payroll_personal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("👨‍💼 Особистий кабінет недоступний: працівника не знайдено.")
        return
    if employee["registration_status"] != "approved":
        await update.message.reply_text(
            "⏳ Вашу реєстрацію очікує підтвердження адміністратора.",
            reply_markup=payroll_pending_menu,
        )
        return
    if not employee["is_active"]:
        await update.message.reply_text("⛔ Ваш профіль працівника деактивовано.")
        return
    menu = payroll_personal_menu_land_manager if employee["role_code"] == "land_manager" else payroll_personal_menu
    await update.message.reply_text(
        f"👨‍💼 Кабінет: {employee['full_name']}\nОберіть дію:",
        reply_markup=menu,
    )


async def payroll_arrived_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("Працівника не знайдено.")
        return
    if employee["registration_status"] != "approved" or not employee["is_active"]:
        await update.message.reply_text("⛔ Дія недоступна до підтвердження/активації профілю.")
        return
    await update.message.reply_text(
        "Надішліть геолокацію (вкладенням Location) для фіксації прибуття.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Надіслати геолокацію", request_location=True)], ["◀️ Назад"]],
            resize_keyboard=True,
        ),
    )


async def payroll_finished_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("Працівника не знайдено.")
        return
    if employee["registration_status"] != "approved" or not employee["is_active"]:
        await update.message.reply_text("⛔ Дія недоступна до підтвердження/активації профілю.")
        return
    context.user_data["attendance_mode"] = "finish"
    await update.message.reply_text(
        "Надішліть геолокацію (вкладенням Location) для фіксації завершення.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Надіслати геолокацію", request_location=True)], ["◀️ Назад"]],
            resize_keyboard=True,
        ),
    )


async def payroll_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee or employee["registration_status"] != "approved" or not employee["is_active"]:
        return
    loc = update.message.location
    mode = context.user_data.get("attendance_mode", "arrive")
    if mode == "finish":
        await upsert_attendance_finish(employee["id"], date.today(), loc.latitude, loc.longitude)
        context.user_data["attendance_mode"] = "arrive"
        await update.message.reply_text("🏁 Завершення роботи зафіксовано з геолокацією.")
    else:
        await upsert_attendance_arrival(employee["id"], date.today(), loc.latitude, loc.longitude)
        await update.message.reply_text("📍 Прибуття зафіксовано з геолокацією.")


async def payroll_my_month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("Працівника не знайдено.")
        return
    if employee["registration_status"] != "approved" or not employee["is_active"]:
        await update.message.reply_text("⛔ Розділ буде доступний після підтвердження/активації профілю.")
        return
    today = date.today()
    period = await get_or_create_payroll_period(today.year, today.month)
    summary = await database.fetch_one(
        EmployeeMonthSummary.select().where(
            (EmployeeMonthSummary.c.employee_id == employee["id"])
            & (EmployeeMonthSummary.c.period_id == period["id"])
        )
    )
    attendance = await get_attendance_by_employee(employee["id"], limit=7)
    att_text = "\n".join([f"{a['date']}: прибув={a['arrived_at']} завершив={a['finished_at']}" for a in attendance])
    if not summary:
        await update.message.reply_text(f"Поточний місяць: підсумок ще не розраховано.\n\nОстання присутність:\n{att_text or '—'}")
        return
    await update.message.reply_text(
        f"Поточний місяць:\nКЕФ: {summary['total_kef']}\nБронювання: {summary['kef_used_for_booking']}\n"
        f"Перебір: {summary['kef_over']}\nНедобір: {summary['kef_shortage']}\nЗП: {summary['salary_amount']}\n"
        f"До виплати: {summary['total_to_pay']}\n\nОстання присутність:\n{att_text or '—'}"
    )


async def payroll_my_results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("Працівника не знайдено.")
        return
    if employee["role_code"] != "land_manager":
        await update.message.reply_text("Результати доступні для ролі «землевпорядник».")
        return
    await update.message.reply_text(
        "🧾 Мої результати:\n• Нова земля\n• Пролонгації\n• Видача орендної плати\n• Історія місяців"
    )


async def payroll_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("Заявку не знайдено. Для реєстрації потрібне запрошення від адміністратора.")
        return
    await update.message.reply_text(
        f"Статус заявки: {employee['registration_status']}.\n"
        f"Роль: {employee['role_code']}.\n"
        f"Активність: {'активний' if employee['is_active'] else 'неактивний'}."
    )


async def payroll_add_employee_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = " ".join(context.args)
    try:
        full_name, role_code, tg_id = [x.strip() for x in payload.split("|")]
        tg_id_int = int(tg_id)
    except Exception:
        await update.message.reply_text("Формат: /payroll_add_employee ПІБ | role_code | telegram_id")
        return
    employee_id = await add_employee(
        {
            "full_name": full_name,
            "telegram_user_id": tg_id_int,
            "role_code": role_code,
            "is_active": True,
            "registration_status": "approved",
            "booking_enabled": True,
            "created_at": datetime.utcnow(),
        }
    )
    await update.message.reply_text(f"Працівника створено, id={employee_id}")


async def payroll_recalc_month_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    period = await get_or_create_payroll_period(today.year, today.month)
    booking_settings = await database.fetch_one(BookingSettings.select().limit(1))
    kef_rules = await database.fetch_all(KefRule.select().order_by(KefRule.c.min_hours))
    employees = await get_employees(active_only=True)

    for emp in employees:
        if emp["registration_status"] != "approved":
            continue
        entries = await get_work_log_entries(period_id=period["id"], employee_id=emp["id"])
        processed_entries = []
        for e in entries:
            operation = None
            if e["operation_id"]:
                operation = await database.fetch_one(
                    OperationsCatalog.select().where(OperationsCatalog.c.id == e["operation_id"])
                )
            salary = calculate_salary_for_log_entry(e, operation, {"payers_rate": 0})
            kef = calculate_kef_for_log_entry(e, kef_rules, role_code=emp["role_code"])
            await database.execute(
                WorkLog.update().where(WorkLog.c.id == e["id"]).values(
                    salary_amount=salary,
                    kef_amount=kef,
                )
            )
            copy_e = dict(e)
            copy_e["salary_amount"] = salary
            copy_e["kef_amount"] = kef
            processed_entries.append(copy_e)

        summary = calculate_employee_month_summary(
            processed_entries,
            booking_settings or {"booking_required_kef": 21, "kef_money_value": 1000, "booking_month_cost": 21000},
        )
        exists = await database.fetch_one(
            EmployeeMonthSummary.select().where(
                (EmployeeMonthSummary.c.employee_id == emp["id"])
                & (EmployeeMonthSummary.c.period_id == period["id"])
            )
        )
        data = {
            "employee_id": emp["id"],
            "period_id": period["id"],
            **summary,
        }
        if exists:
            await database.execute(
                EmployeeMonthSummary.update().where(EmployeeMonthSummary.c.id == exists["id"]).values(**data)
            )
        else:
            await database.execute(EmployeeMonthSummary.insert().values(**data))

    await update.message.reply_text("✅ Місячні нарахування перераховано.")


async def payroll_add_log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = " ".join(context.args)
    try:
        chunks = [x.strip() for x in payload.split("|")]
        employee_id = int(chunks[0])
        work_type = chunks[1]
        hours = Decimal(chunks[2]) if len(chunks) > 2 and chunks[2] else Decimal("0")
        hectares = Decimal(chunks[3]) if len(chunks) > 3 and chunks[3] else Decimal("0")
        operation_id = int(chunks[4]) if len(chunks) > 4 and chunks[4] else None
    except Exception:
        await update.message.reply_text("Формат: /payroll_add_log employee_id|work_type|hours|hectares|operation_id")
        return

    today = date.today()
    period = await get_or_create_payroll_period(today.year, today.month)
    log_id = await add_work_log_entry(
        {
            "employee_id": employee_id,
            "period_id": period["id"],
            "date": today,
            "work_type": work_type,
            "hours_worked": hours,
            "hectares": hectares,
            "operation_id": operation_id,
            "source_type": "manual",
            "created_by": update.effective_user.id,
        }
    )
    await update.message.reply_text(f"✅ Додано запис work_log #{log_id}")


async def payroll_invite_create_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = await get_user_by_tg_id(query.from_user.id)
    if not user or user["role"] != "admin":
        await query.answer("Лише для admin", show_alert=True)
        return
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Механізатор", callback_data="empinvite:create:tractor_driver")],
        [InlineKeyboardButton("Землевпорядник", callback_data="empinvite:create:land_manager")],
        [InlineKeyboardButton("Без фіксації ролі", callback_data="empinvite:create:none")],
    ]
    await query.message.edit_text("Оберіть роль для запрошення:", reply_markup=InlineKeyboardMarkup(keyboard))


async def payroll_invite_create_role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = await get_user_by_tg_id(query.from_user.id)
    if not user or user["role"] != "admin":
        await query.answer("Лише для admin", show_alert=True)
        return
    role_code = query.data.split(":")[-1]
    role_code = None if role_code == "none" else role_code
    _, token = await create_employee_invite(query.from_user.id, role_preselected=role_code)
    bot_name = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_name}?start=empinvite_{token}"
    await query.answer("Запрошення створено")
    await query.message.edit_text(
        f"✅ Запрошення створено.\nРоль: {role_code or 'без фіксації'}\nПосилання:\n{invite_link}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="admin_users")]]),
    )


async def payroll_registration_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    payload = context.args[0] if context.args else ""
    if not payload.startswith("empinvite_"):
        return False
    token = payload.removeprefix("empinvite_")
    invite = await get_employee_invite(token)
    if not invite:
        await update.message.reply_text("❌ Запрошення не знайдено.")
        return True
    if invite["is_used"]:
        await update.message.reply_text("❌ Це запрошення вже використано.")
        return True
    if invite["expires_at"] and datetime.utcnow() > invite["expires_at"]:
        await update.message.reply_text("❌ Термін дії запрошення завершився.")
        return True
    context.user_data["employee_registration"] = {
        "invite_id": invite["id"],
        "role_preselected": invite["role_preselected"],
        "step": "full_name",
    }
    await update.message.reply_text("Реєстрація працівника.\nВведіть ПІБ:")
    return True


async def payroll_registration_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg = context.user_data.get("employee_registration")
    if not reg:
        return
    text = (update.message.text or "").strip()
    if reg["step"] == "full_name":
        reg["full_name"] = text
        reg["step"] = "phone"
        await update.message.reply_text("Введіть номер телефону:")
        return
    if reg["step"] == "phone":
        reg["phone"] = text
        if reg.get("role_preselected"):
            reg["role_code"] = reg["role_preselected"]
            reg["step"] = "confirm"
            await update.message.reply_text(
                f"Підтвердіть дані:\nПІБ: {reg['full_name']}\nТелефон: {reg['phone']}\nРоль: {reg['role_code']}\n\nНапишіть: ТАК"
            )
            return
        reg["step"] = "role"
        await update.message.reply_text("Оберіть роль кодом: tractor_driver / land_manager / operations_worker")
        return
    if reg["step"] == "role":
        reg["role_code"] = text
        reg["step"] = "confirm"
        await update.message.reply_text(
            f"Підтвердіть дані:\nПІБ: {reg['full_name']}\nТелефон: {reg['phone']}\nРоль: {reg['role_code']}\n\nНапишіть: ТАК"
        )
        return
    if reg["step"] == "confirm":
        if text.lower() != "так":
            await update.message.reply_text("Скасовано. Для повтору перейдіть по запрошенню ще раз.")
            context.user_data.pop("employee_registration", None)
            return
        user = await get_user_by_tg_id(update.effective_user.id)
        user_id = user["id"] if user else None
        employee_id = await upsert_employee_by_telegram_id(
            update.effective_user.id,
            {
                "user_id": user_id,
                "telegram_user_id": update.effective_user.id,
                "full_name": reg["full_name"],
                "phone": reg["phone"],
                "role_code": reg["role_code"],
                "is_active": False,
                "registration_status": "pending",
                "booking_enabled": True,
                "created_at": datetime.utcnow(),
            },
        )
        await mark_invite_used(reg["invite_id"], update.effective_user.id)
        context.user_data.pop("employee_registration", None)
        await update.message.reply_text("⏳ Вашу реєстрацію очікує підтвердження адміністратора.", reply_markup=payroll_pending_menu)
        await _notify_admins_about_request(context, employee_id)


async def _notify_admins_about_request(context: ContextTypes.DEFAULT_TYPE, employee_id: int):
    employee = await get_employee(employee_id)
    admins_users = await database.fetch_all(sqlalchemy.text('SELECT telegram_id FROM "user" WHERE role = :r AND is_active = TRUE'), {"r": "admin"})
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Підтвердити", callback_data=f"empreg:approve:{employee_id}")],
            [InlineKeyboardButton("❌ Відхилити", callback_data=f"empreg:reject:{employee_id}")],
        ]
    )
    text = (
        "🆕 Нова заявка працівника\n\n"
        f"ПІБ: {employee['full_name']}\n"
        f"Телефон: {employee['phone'] or '—'}\n"
        f"Роль: {employee['role_code']}\n"
        f"Telegram ID: {employee['telegram_user_id']}"
    )
    for admin in admins_users:
        await context.bot.send_message(chat_id=admin["telegram_id"], text=text, reply_markup=keyboard)


async def payroll_employee_approve_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = await get_user_by_tg_id(query.from_user.id)
    if not user or user["role"] != "admin":
        await query.answer("Лише для admin", show_alert=True)
        return
    employee_id = int(query.data.split(":")[-1])
    employee = await get_employee(employee_id)
    if not employee:
        await query.answer("Заявку не знайдено", show_alert=True)
        return
    await update_employee(
        employee_id,
        {
            "registration_status": "approved",
            "is_active": True,
            "approved_at": datetime.utcnow(),
            "approved_by": query.from_user.id,
        },
    )
    await log_admin_action(query.from_user.id, f"employee_approve {employee_id}")
    await query.answer("Підтверджено")
    await query.message.edit_text(f"✅ Заявку #{employee_id} підтверджено.")
    await context.bot.send_message(
        chat_id=employee["telegram_user_id"],
        text="✅ Реєстрацію підтверджено. Вам відкрито особистий кабінет у модулі 💼 Облік ЗП.",
    )


async def payroll_employee_reject_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = await get_user_by_tg_id(query.from_user.id)
    if not user or user["role"] != "admin":
        await query.answer("Лише для admin", show_alert=True)
        return
    employee_id = int(query.data.split(":")[-1])
    employee = await get_employee(employee_id)
    if not employee:
        await query.answer("Заявку не знайдено", show_alert=True)
        return
    await update_employee(employee_id, {"registration_status": "rejected", "is_active": False})
    await log_admin_action(query.from_user.id, f"employee_reject {employee_id}")
    await query.answer("Відхилено")
    await query.message.edit_text(f"❌ Заявку #{employee_id} відхилено.")
    await context.bot.send_message(
        chat_id=employee["telegram_user_id"],
        text="❌ Реєстрацію відхилено адміністратором. Зверніться до адміністратора.",
    )
