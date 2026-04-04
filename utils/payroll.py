from decimal import Decimal
from typing import Any


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def calculate_kef_for_log_entry(entry: dict, kef_rules: list[dict], *, role_code: str | None = None) -> Decimal:
    include_mode = entry.get("include_in_kef_mode") or "time"
    if include_mode == "none":
        return Decimal("0")
    if include_mode == "manual":
        return _dec(entry.get("kef_amount"))

    hours = _dec(entry.get("hours_worked"))
    late_minutes = int(entry.get("late_minutes") or 0)
    late_compensated = bool(entry.get("late_compensated"))
    if late_minutes > 0 and not late_compensated:
        hours -= (Decimal(late_minutes) / Decimal(60))
    if hours < 0:
        hours = Decimal("0")

    applicable = [
        rule for rule in kef_rules
        if rule.get("role_code") in (None, role_code)
    ]
    applicable.sort(key=lambda x: _dec(x.get("min_hours")))
    for rule in applicable:
        if _dec(rule["min_hours"]) <= hours < _dec(rule["max_hours"]):
            kef_value = _dec(rule["kef_value"])
            if entry.get("work_type") == "planned_repair":
                return min(kef_value, Decimal("1"))
            return kef_value
    if hours >= Decimal("24"):
        return Decimal("2")
    return Decimal("0")


def calculate_salary_for_log_entry(entry: dict, operation: dict | None, settings: dict) -> Decimal:
    work_type = entry.get("work_type")
    hours = _dec(entry.get("hours_worked"))
    hectares = _dec(entry.get("hectares"))
    machine_hours = _dec(entry.get("machine_hours"))
    units_count = _dec(entry.get("units_count"))
    payers_count = _dec(entry.get("payers_count"))

    if work_type == "planned_repair":
        return Decimal("500") if hours < Decimal("4") else Decimal("1000")

    if work_type == "roman_time":
        if hours < Decimal("6"):
            return Decimal("500")
        if hours < Decimal("12"):
            return Decimal("1000")
        return Decimal("1500")

    if work_type == "manual_amount":
        return _dec(entry.get("manual_amount"))

    if not operation:
        return Decimal("0")

    operation_type = operation.get("operation_type")
    rate_value = _dec(operation.get("rate_value"))

    if operation_type == "field_piecework":
        base_units = hectares if operation.get("unit_type") == "hectare" else machine_hours
        return base_units * rate_value

    if operation_type == "contract_area_years":
        years = _dec(entry.get("units_count"), default="1")
        return hectares * years * rate_value

    if operation_type == "contract_count":
        return units_count * rate_value

    if operation_type == "payers_count":
        payer_rate = _dec(settings.get("payers_rate"), default="0")
        return payers_count * payer_rate

    return _dec(entry.get("manual_amount"))


def apply_booking_coverage(total_kef: Decimal, booking_settings: dict) -> dict:
    required_kef = _dec(booking_settings.get("booking_required_kef"), default="21")
    kef_money_value = _dec(booking_settings.get("kef_money_value"), default="1000")
    booking_month_cost = _dec(booking_settings.get("booking_month_cost"), default="21000")

    kef_used = min(total_kef, required_kef)
    covered_amount = kef_used * kef_money_value
    shortage = max(required_kef - total_kef, Decimal("0"))
    overflow = max(total_kef - required_kef, Decimal("0"))
    uncovered = max(booking_month_cost - covered_amount, Decimal("0"))

    return {
        "kef_used_for_booking": kef_used,
        "booking_covered_amount": covered_amount,
        "kef_shortage": shortage,
        "kef_over": overflow,
        "booking_uncovered_amount": uncovered,
    }


def apply_kef_overflow_decision(kef_over: Decimal, decision: str, kef_money_value: Decimal) -> dict:
    if kef_over <= 0:
        return {"kef_to_next_month": Decimal("0"), "kef_over_paid_amount": Decimal("0")}

    if decision == "pay":
        return {"kef_to_next_month": Decimal("0"), "kef_over_paid_amount": kef_over * kef_money_value}
    if decision == "carry":
        return {"kef_to_next_month": kef_over, "kef_over_paid_amount": Decimal("0")}
    return {"kef_to_next_month": Decimal("0"), "kef_over_paid_amount": Decimal("0")}


def calculate_employee_month_summary(entries: list[dict], booking_settings: dict, *,
                                     kef_from_prev_month: Decimal = Decimal("0"),
                                     bonus_amount: Decimal = Decimal("0"),
                                     fine_amount: Decimal = Decimal("0"),
                                     overflow_decision: str = "no_decision") -> dict:
    total_kef = kef_from_prev_month + sum((_dec(e.get("kef_amount")) for e in entries), Decimal("0"))
    salary_amount = sum((_dec(e.get("salary_amount")) for e in entries), Decimal("0"))

    coverage = apply_booking_coverage(total_kef, booking_settings)
    overflow_resolution = apply_kef_overflow_decision(
        coverage["kef_over"],
        overflow_decision,
        _dec(booking_settings.get("kef_money_value"), default="1000"),
    )

    total_to_pay = salary_amount + bonus_amount - fine_amount + overflow_resolution["kef_over_paid_amount"]
    return {
        "total_kef": total_kef,
        "kef_from_prev_month": kef_from_prev_month,
        "salary_amount": salary_amount,
        "bonus_amount": bonus_amount,
        "fine_amount": fine_amount,
        "total_to_pay": total_to_pay,
        "kef_over_decision": overflow_decision,
        **coverage,
        **overflow_resolution,
    }
