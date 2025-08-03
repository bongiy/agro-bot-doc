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
