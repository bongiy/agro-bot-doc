TEMPLATE_VARIABLES = {
    "payer": {
        "title": "PAYOVYK",
        "items": [
            ("{{payer_full_name}}", "ПІБ"),
            ("{{payer_passport}}", "паспортні дані"),
            ("{{payer_tax_code}}", "ІПН"),
            ("{{payer_address}}", "адреса"),
            ("{{payer_phone}}", "телефон"),
            ("{{payer_birth_date}}", "дата народження"),
        ],
    },
    "agreement": {
        "title": "AGREEMENT",
        "items": [
            ("{{agreement_number}}", "номер"),
            ("{{agreement_date}}", "дата підписання"),
            ("{{agreement_start}}", "дата початку дії"),
            ("{{agreement_end}}", "дата завершення дії"),
            ("{{agreement_type}}", "тип договору"),
            ("{{agreement_notes}}", "нотатки"),
        ],
    },
    "land": {
        "title": "LAND",
        "items": [
            ("{{land_list}}", "список кадастрових номерів"),
            ("{{land_table}}", "HTML-таблиця ділянок (№, площа, НГО)"),
            ("{{total_area}}", "сумарна площа, га"),
            ("{{plot_location}}", "місце розташування ділянки"),
        ],
    },
    "company": {
        "title": "COMPANY",
        "items": [
            ("{{company_name}}", "назва ТОВ"),
            ("{{company_director}}", "директор"),
            ("{{company_code}}", "ЄДРПОУ"),
            ("{{company_address}}", "адреса"),
            ("{{company_iban}}", "рахунок"),
            ("{{company_phone}}", "телефон"),
        ],
    },
}
