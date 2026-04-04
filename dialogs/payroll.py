from datetime import date
from decimal import Decimal

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
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
    database,
    get_attendance_by_employee,
    get_employee_by_tg_id,
    get_employees,
    get_employee_tasks,
    get_or_create_payroll_period,
    get_work_log_entries,
    upsert_attendance_arrival,
    upsert_attendance_finish,
)
from keyboards.menu import payroll_menu, payroll_personal_menu
from utils.payroll import (
    calculate_employee_month_summary,
    calculate_kef_for_log_entry,
    calculate_salary_for_log_entry,
)


async def payroll_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💼 Облік ЗП", reply_markup=payroll_menu)


async def payroll_employees_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employees = await get_employees(active_only=False)
    if not employees:
        await update.message.reply_text(
            "Працівників ще немає. Для створення використайте /payroll_add_employee ІМ'Я | role_code | telegram_id"
        )
        return
    lines = [f"• {e['full_name']} ({e['role_code']}) {'✅' if e['is_active'] else '⛔'}" for e in employees]
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
    await update.message.reply_text(
        f"👨‍💼 Кабінет: {employee['full_name']}\nОберіть дію:",
        reply_markup=payroll_personal_menu,
    )


async def payroll_arrived_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = await get_employee_by_tg_id(update.effective_user.id)
    if not employee:
        await update.message.reply_text("Працівника не знайдено.")
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
    if not employee:
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
            "booking_enabled": True,
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
        # employee_id|work_type|hours|hectares|operation_id(optional)
        chunks = [x.strip() for x in payload.split("|")]
        employee_id = int(chunks[0])
        work_type = chunks[1]
        hours = Decimal(chunks[2])
        hectares = Decimal(chunks[3]) if len(chunks) > 3 and chunks[3] else None
        operation_id = int(chunks[4]) if len(chunks) > 4 and chunks[4] else None
    except Exception:
        await update.message.reply_text("Формат: /payroll_add_log employee_id|work_type|hours|hectares|operation_id")
        return

    today = date.today()
    period = await get_or_create_payroll_period(today.year, today.month)
    entry_id = await add_work_log_entry(
        {
            "employee_id": employee_id,
            "period_id": period["id"],
            "date": today,
            "work_type": work_type,
            "operation_id": operation_id,
            "hours_worked": hours,
            "hectares": hectares,
            "source_type": "manual",
            "source_id": None,
            "created_by": update.effective_user.id,
            "late_minutes": 0,
            "late_compensated": False,
            "include_in_kef_mode": "time",
        }
    )
    await update.message.reply_text(f"Запис у журнал робіт додано: #{entry_id}")
