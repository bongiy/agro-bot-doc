# Telegram Bot with Webhooks Template

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![PyCharm](https://img.shields.io/badge/pycharm-143?style=for-the-badge&logo=pycharm&logoColor=black&color=black&labelColor=green)

This template provides a basic framework for creating a Telegram bot using FastAPI, connecting it to Telegram's Webhook
system.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/5kprwG?referralCode=Al2B-n)

## ✨ Features

- **FastAPI**: Lightweight, fast web framework for building APIs.
- **[Python Telegram Bot](https://python-telegram-bot.org/)**: Seamless integration with Telegram's Bot API.
- **Webhook Support**: Automatic webhook setup and processing of Telegram updates using the `telegram.ext.Application`.

## 💁‍♀️ How to install

- Create a new repository from this template: Click
  the [Use this template](https://github.com/new?template_name=TelegramBot.Webhook&template_owner=dangos-dev) button on
  this repository's main page (or clone the repository).
- Install packages with pip using `pip install -r requirements.txt`
- Run locally using `hypercorn main:app --reload`

## 🤖 Example
Talk to [DangoBot - Telegram Webhooks](https://t.me/dango_webhook_bot) on Telegram

## Contract template variables

Available placeholders for agreement templates. If a value is missing, the bot
will insert `______________________` in the document so it can be filled in
manually.

### Company
- `{{company_name}}` — Назва ТОВ
- `{{company_code}}` — ЄДРПОУ
- `{{company_address}}` — Юридична адреса
- `{{company_director}}` — ПІБ директора
- `{{company_director_gen}}` — ПІБ директора у формі "від імені..."
- `{{company_logo}}` — Логотип ТОВ

### Contract
- `{{contract_number}}` — Номер договору (0001/2025)
- `{{contract_date_signed}}` — Дата підписання договору
- `{{contract_date_from}}` — Дата початку дії договору
- `{{contract_date_to}}` — Дата закінчення дії договору
- `{{contract_term}}` — Строк дії договору (у роках)
- `{{contract_rent}}` — Сума орендної плати

### Payer
- `{{payer_name}}` — ПІБ пайовика
- `{{payer_tax_id}}` — ІПН пайовика
- `{{payer_birthdate}}` — Дата народження пайовика
- `{{payer_passport}}` — Паспортні дані пайовика
- `{{payer_address}}` — Адреса проживання пайовика
- `{{payer_share}}` — Частка власності пайовика
- `{{payer_phone}}` — Номер телефону пайовика
- `{{payer_bank_card}}` — Банківська картка пайовика
- `{{payers_list}}` — Таблиця пайовиків з частками

### Land plot
- `{{plot_cadastre}}` — Кадастровий номер ділянки
- `{{plot_area}}` — Площа ділянки (в га)
- `{{plot_share}}` — Частка ділянки в договорі
- `{{plot_ngo}}` — НГО (грн)
- `{{plot_location}}` — Сільська рада, район, область
- `{{plots_table}}` — Таблиця ділянок

### Service
- `{{today}}` — Поточна дата
- `{{year}}` — Поточний рік

## Contract generation

Use `contract_pdf.generate_contract()` to render a DOCX template with variables
and convert it to PDF. The resulting file is uploaded to FTP or saved locally in
development mode.
