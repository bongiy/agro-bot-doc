from io import BytesIO
from typing import Iterable


async def payments_to_excel(rows: Iterable[dict]) -> BytesIO:
    """Generate Excel file from payment rows.

    Each row must contain keys: payment_date, payer_name, company_name,
    amount, status, is_heir.
    """
    # Import here to avoid hard dependency during module import
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "Пайовик", "Компанія", "Сума", "Статус", "Спадкоємець"])
    for r in rows:
        ws.append(
            [
                r["payment_date"].strftime("%d.%m.%Y"),
                r["payer_name"],
                r["company_name"],
                float(r["amount"] or 0),
                r["status"],
                "так" if r["is_heir"] else "ні",
            ]
        )
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio
