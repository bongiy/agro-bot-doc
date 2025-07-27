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
        ],
    },
    "payer": {
        "title": "Пайовики",
        "items": [
            ("{{payer_name}}", "ПІБ пайовика"),
            ("{{payer_passport}}", "Паспортні дані"),
            ("{{payer_address}}", "Адреса"),
            ("{{payer_share}}", "Частка"),
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
