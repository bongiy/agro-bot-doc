"""Variables for contract templates and placeholder for empty fields."""

# Default placeholder to use when a value is missing
EMPTY_VALUE = "______________________"

MONTHS_UA = [
    "січня", "лютого", "березня", "квітня",
    "травня", "червня", "липня", "серпня",
    "вересня", "жовтня", "листопада", "грудня",
]

TEMPLATE_VARIABLES = {
    "company": {
        "title": "ТОВ",
        "items": [
            ("{{company_name}}", "Назва ТОВ"),
            ("{{company_code}}", "ЄДРПОУ"),
            ("{{company_address}}", "Юридична адреса"),
            ("{{company_director}}", "ПІБ директора"),
            ("{{company_director_gen}}", "ПІБ у формі \"від імені...\""),
            ("{{company_logo}}", "Логотип ТОВ"),
        ],
    },
    "contract": {
        "title": "Договір",
        "items": [
            ("{{contract_number}}", "Номер договору"),
            ("{{contract_date_signed}}", "Дата підписання"),
            ("{{contract_date_from}}", "Початок дії"),
            ("{{contract_date_to}}", "Кінець дії"),
            ("{{contract_term}}", "Строк дії"),
            ("{{contract_rent}}", "Сума орендної плати"),
        ],
    },
    "payer": {
        "title": "Пайовики",
        "items": [
            ("{{payer_name}}", "ПІБ пайовика"),
            ("{{payer_tax_id}}", "ІПН"),
            ("{{payer_birthdate}}", "Дата народження"),
            ("{{payer_passport}}", "Паспортні дані"),
            ("{{payer_address}}", "Адреса"),
            ("{{payer_share}}", "Частка"),
            ("{{payer_phone}}", "Телефон"),
            ("{{payer_bank_card}}", "Банківська картка"),
            ("{{payers_list}}", "Таблиця пайовиків"),
        ],
    },
    "plot": {
        "title": "Ділянки",
        "items": [
            ("{{plot_cadastre}}", "Кадастровий номер"),
            ("{{plot_area}}", "Площа"),
            ("{{plot_share}}", "Частка по договору"),
            ("{{plot_ngo}}", "НГО"),
            ("{{plot_location}}", "Територія"),
            ("{{plots_table}}", "Таблиця ділянок"),
        ],
    },
    "service": {
        "title": "Службові",
        "items": [
            ("{{today}}", "Поточна дата"),
            ("{{year}}", "Поточний рік"),
        ],
    },
}


def with_default(value: str | None) -> str:
    """Return placeholder if value is empty."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return EMPTY_VALUE
    return value


def date_to_words(date_str: str | None) -> str:
    """Convert DD.MM.YYYY to 'DD <month> YYYY' in Ukrainian."""
    if not date_str:
        return EMPTY_VALUE
    try:
        from datetime import datetime

        dt = datetime.strptime(date_str, "%d.%m.%Y")
    except Exception:
        return date_str
    month_name = MONTHS_UA[dt.month - 1]
    return f"{dt.day} {month_name} {dt.year}"

