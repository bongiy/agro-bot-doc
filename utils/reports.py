from io import BytesIO
from typing import Iterable


async def payments_to_excel(rows: Iterable[dict]) -> BytesIO:
    """Generate Excel file from payment rows and return as BytesIO."""
    # Import here to avoid hard dependency during module import
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "Пайовик", "Компанія", "Сума", "Статус", "Спадкоємець"])
    total = 0.0
    for r in rows:
        amount = float(r.get("amount") or 0)
        total += amount
        date_val = (
            r.get("payment_date").strftime("%d.%m.%Y")
            if r.get("payment_date")
            else ""
        )
        ws.append(
            [
                date_val,
                r.get("payer_name") or "",
                r.get("company_name") or "",
                amount,
                r.get("status") or "",
                "так" if r.get("is_heir") else "ні",
            ]
        )
        # Set currency format for the last added amount cell
        ws.cell(row=ws.max_row, column=4).number_format = "0.00"
    # Summary row
    ws.append(["", "", "Разом", total, "", ""])
    ws.cell(row=ws.max_row, column=4).number_format = "0.00"
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


async def rent_summary_to_excel(rows: Iterable[dict]) -> BytesIO:
    """Generate Excel file for rent summary report."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "Компанія",
            "Договорів",
            "Пайовиків",
            "Ділянок",
            "Нараховано",
            "Виплачено",
            "Борг",
            "Очікує",
            "Частково",
            "Оплачено",
        ]
    )
    totals = [0] * 6  # rent_total, paid_total, debt, pending, partial, paid
    for r in rows:
        debt = float(r.get("rent_total", 0)) - float(r.get("paid_total", 0))
        ws.append(
            [
                r.get("name"),
                r.get("contracts"),
                r.get("payers"),
                r.get("plots"),
                float(r.get("rent_total", 0)),
                float(r.get("paid_total", 0)),
                debt,
                float(r.get("pending_amount", 0)),
                float(r.get("partial_amount", 0)),
                float(r.get("paid_amount", 0)),
            ]
        )
        row = ws.max_row
        for col in range(5, 11):
            ws.cell(row=row, column=col).number_format = "0.00"
        totals[0] += float(r.get("rent_total", 0))
        totals[1] += float(r.get("paid_total", 0))
        totals[2] += debt
        totals[3] += float(r.get("pending_amount", 0))
        totals[4] += float(r.get("partial_amount", 0))
        totals[5] += float(r.get("paid_amount", 0))
    ws.append(
        [
            "Разом",
            "",
            "",
            "",
            *totals,
        ]
    )
    last_row = ws.max_row
    for col in range(5, 11):
        ws.cell(row=last_row, column=col).number_format = "0.00"
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio
