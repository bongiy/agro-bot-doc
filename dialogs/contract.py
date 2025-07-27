import os
import unicodedata
import re
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile,
)
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from db import (
    database,
    Company,
    Contract,
    ContractLandPlot,
    LandPlot,
    LandPlotOwner,
    Payer,
)
from keyboards.menu import contracts_menu
from dialogs.post_creation import prompt_add_docs
from ftp_utils import download_file_ftp
import sqlalchemy

CHOOSE_COMPANY, SET_DURATION, SET_VALID_FROM, CHOOSE_PAYER, INPUT_LANDS, SEARCH_LAND = range(6)

BACK_BTN = "◀️ Назад"  # ◀️ Назад
CANCEL_BTN = "❌ Скасувати"  # ❌ Скасувати


def to_latin_filename(text: str, default: str = "document.pdf") -> str:
    name = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    name = name.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    if not name or name.startswith(".pdf") or name.lower() == ".pdf":
        return default
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def format_cadaster(text: str) -> str | None:
    """Normalize cadastral number to XXXXXX:XX:XXX:XXXX format."""
    digits = re.sub(r"\D", "", text)
    if len(digits) != 19:
        return None
    return f"{digits[:10]}:{digits[10:12]}:{digits[12:15]}:{digits[15:]}"


async def back_or_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, step_back: int):
    """Handle back/cancel buttons for contract creation."""
    text = update.message.text if update.message else None
    if text == CANCEL_BTN:
        await update.message.reply_text(
            "⚠️ Створення договору скасовано. Дані не збережено.",
            reply_markup=contracts_menu,
        )
        context.user_data.clear()
        return ConversationHandler.END
    if text == BACK_BTN:
        return step_back
    return None


async def search_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cadastral search within contract FSM."""
    result = await back_or_cancel(update, context, INPUT_LANDS)
    if result is not None:
        return result
    cad = format_cadaster(update.message.text)
    if not cad:
        await update.message.reply_text("Некоректний кадастровий номер. Спробуйте ще:")
        return SEARCH_LAND
    row = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.cadaster == cad))
    if not row:
        await update.message.reply_text("Ділянку не знайдено.")
        return INPUT_LANDS
    btn = InlineKeyboardButton("➕ Додати до договору", callback_data=f"add_land_to_contract:{row['id']}")
    await update.message.reply_text(
        f"ID {row['id']}: {row['cadaster']} — {row['area']:.4f} га",
        reply_markup=InlineKeyboardMarkup([[btn]]),
    )
    return INPUT_LANDS


async def add_land_from_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user adds land from search results."""
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    context.user_data.setdefault("land_ids", []).append(land_id)
    await query.answer("Додано до договору")
    land_list = " ".join(map(str, context.user_data["land_ids"]))
    await query.message.reply_text(
        f"Ділянка #{land_id} додана. Поточний список: {land_list}",
        reply_markup=ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
    )
    return INPUT_LANDS


async def send_contract_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, _, contract_id, fname = query.data.split(":", 3)
    filename = to_latin_filename(fname)
    remote_path = f"contracts/{contract_id}/{filename}"
    tmp_path = f"temp_docs/{filename}"
    try:
        os.makedirs("temp_docs", exist_ok=True)
        download_file_ftp(remote_path, tmp_path)
        await query.message.reply_document(document=InputFile(tmp_path), filename=filename)
        os.remove(tmp_path)
    except Exception as e:  # pragma: no cover - just user notification
        await query.answer(f"Помилка при скачуванні файлу: {e}", show_alert=True)


# ==== ДОДАВАННЯ ДОГОВОРУ ====
async def add_contract_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    companies = await database.fetch_all(sqlalchemy.select(Company))
    if not companies:
        await update.message.reply_text("Спочатку додайте хоча б одне ТОВ!", reply_markup=contracts_menu)
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup(
        [[f"{c['id']}: {c['short_name'] or c['full_name']}"] for c in companies] + [[CANCEL_BTN]],
        resize_keyboard=True,
    )
    context.user_data["companies"] = {f"{c['id']}: {c['short_name'] or c['full_name']}": c["id"] for c in companies}
    await update.message.reply_text("Оберіть ТОВ-орендаря:", reply_markup=kb)
    return CHOOSE_COMPANY


async def choose_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, CHOOSE_COMPANY)
    if result is not None:
        return result
    company_id = context.user_data["companies"].get(update.message.text)
    if not company_id:
        await update.message.reply_text("Оберіть компанію зі списку:")
        return CHOOSE_COMPANY
    year = datetime.utcnow().year
    rows = await database.fetch_all(
        sqlalchemy.select(Contract.c.number).where(
            (Contract.c.company_id == company_id) & Contract.c.number.like(f"%/{year}")
        )
    )
    max_num = 0
    for r in rows:
        try:
            n = int(str(r["number"]).split("/")[0])
            if n > max_num:
                max_num = n
        except Exception:
            continue
    number = f"{max_num + 1:04d}/{year}"
    context.user_data["company_id"] = company_id
    context.user_data["contract_number"] = number
    await update.message.reply_text(
        f"Номер договору: <b>{number}</b>\nВведіть строк дії в роках:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
    )
    return SET_DURATION


async def set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, CHOOSE_COMPANY)
    if result is not None:
        return result
    try:
        years = int(update.message.text)
        if years <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введіть ціле число років:")
        return SET_DURATION
    context.user_data["duration"] = years
    kb = ReplyKeyboardMarkup(
        [["Від сьогодні"], ["З 1 січня наступного року"], [BACK_BTN, CANCEL_BTN]],
        resize_keyboard=True,
    )
    await update.message.reply_text("Дата набрання чинності:", reply_markup=kb)
    return SET_VALID_FROM


async def set_valid_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, SET_DURATION)
    if result is not None:
        return result
    text = update.message.text
    today = datetime.utcnow().date()
    if text == "Від сьогодні":
        valid_from = today
    else:
        valid_from = datetime(today.year + 1, 1, 1).date()
    duration = context.user_data["duration"]
    valid_to = valid_from + timedelta(days=365 * duration)
    context.user_data["valid_from"] = datetime.combine(valid_from, datetime.min.time())
    context.user_data["valid_to"] = datetime.combine(valid_to, datetime.min.time())
    payers = await database.fetch_all(
        sqlalchemy.select(Payer).order_by(Payer.c.id.desc()).limit(3)
    )
    kb = ReplyKeyboardMarkup(
        [[f"{p['id']}: {p['name']}"] for p in payers]
        + [["🔍 Пошук пайовика"], ["➕ Створити пайовика"], [BACK_BTN, CANCEL_BTN]],
        resize_keyboard=True,
    )
    context.user_data["recent_payers"] = {
        f"{p['id']}: {p['name']}": p["id"] for p in payers
    }
    await update.message.reply_text("Оберіть пайовика:", reply_markup=kb)
    return CHOOSE_PAYER


async def choose_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, SET_VALID_FROM)
    if result is not None:
        return result

    text = update.message.text
    payer_id = context.user_data.get("recent_payers", {}).get(text)
    if payer_id:
        context.user_data["payer_id"] = payer_id
    elif text in ("🔍 Пошук пайовика", "➕ Створити пайовика"):
        await update.message.reply_text("🔜 Функція в розробці")
        return CHOOSE_PAYER
    else:
        await update.message.reply_text("Оберіть варіант зі списку")
        return CHOOSE_PAYER

    lands = await database.fetch_all(
        sqlalchemy.select(LandPlot).where(LandPlot.c.payer_id == payer_id)
    )
    context.user_data["land_ids"] = []
    if lands:
        land_list = " ".join(str(l["id"]) for l in lands)
        msg = (
            f"Ділянки пайовика: {land_list}\n"
            "Вкажіть ID ділянок через пробіл або скористайтеся пошуком."
        )
    else:
        msg = "У цього пайовика немає ділянок. Вкажіть ID вручну або скористайтеся пошуком."
    kb = ReplyKeyboardMarkup(
        [["🔍 Пошук ділянки", "✅ Завершити"], [BACK_BTN, CANCEL_BTN]],
        resize_keyboard=True,
    )
    await update.message.reply_text(msg, reply_markup=kb)
    return INPUT_LANDS


async def save_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, CHOOSE_PAYER)
    if result is not None:
        return result
    text = update.message.text
    if text == "🔍 Пошук ділянки":
        await update.message.reply_text(
            "Введіть кадастровий номер:",
            reply_markup=ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
        )
        return SEARCH_LAND
    if text == "✅ Завершити":
        land_ids = context.user_data.get("land_ids", [])
        if not land_ids:
            await update.message.reply_text("Не додано жодної ділянки.")
            return INPUT_LANDS
    else:
        try:
            new_ids = [int(i) for i in text.replace(",", " ").split() if i]
        except ValueError:
            await update.message.reply_text("Невірний формат. Введіть ID через пробіл:")
            return INPUT_LANDS
        if not new_ids:
            await update.message.reply_text("Не вказано жодної ділянки. Спробуйте ще раз:")
            return INPUT_LANDS
        context.user_data.setdefault("land_ids", []).extend(new_ids)
        land_list = " ".join(map(str, context.user_data["land_ids"]))
        await update.message.reply_text(
            f"Додано: {' '.join(map(str, new_ids))}. Поточний список: {land_list}\nНатисніть '✅ Завершити' коли закінчите.",
            reply_markup=ReplyKeyboardMarkup([["🔍 Пошук ділянки", "✅ Завершити"], [BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
        )
        return INPUT_LANDS
        
    land_ids = context.user_data.get("land_ids", [])
    invalid = []
    for lid in land_ids:
        total = await database.fetch_val(
            sqlalchemy.select(sqlalchemy.func.sum(LandPlotOwner.c.share)).where(
                LandPlotOwner.c.land_plot_id == lid
            )
        )
        if total is None or abs(total - 1.0) > 0.01:
            invalid.append(lid)
    if invalid:
        await update.message.reply_text(
            f"⚠️ Не охоплено 100% частки по ділянках: {', '.join(map(str, invalid))}"
        )
        return INPUT_LANDS
    now = datetime.utcnow()
    contract_id = await database.execute(
        Contract.insert().values(
            company_id=context.user_data["company_id"],
            number=context.user_data["contract_number"],
            date_signed=now,
            date_valid_from=context.user_data["valid_from"],
            date_valid_to=context.user_data["valid_to"],
            duration_years=context.user_data["duration"],
            created_at=now,
        )
    )
    for lid in land_ids:
        await database.execute(
            ContractLandPlot.insert().values(contract_id=contract_id, land_plot_id=lid)
        )
    context.user_data.clear()
    await prompt_add_docs(
        update,
        context,
        "contract",
        contract_id,
        "Договір успішно створено!",
        contracts_menu,
    )
    return ConversationHandler.END


add_contract_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Створити договір$"), add_contract_start)],
    states={
        CHOOSE_COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_company)],
        SET_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_duration)],
        SET_VALID_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_valid_from)],
        CHOOSE_PAYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_payer)],
        INPUT_LANDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_contract),
            CallbackQueryHandler(add_land_from_search, pattern=r"^add_land_to_contract:\d+$"),
        ],
        SEARCH_LAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_land)],
    },
    fallbacks=[],
)


# ==== СПИСОК ТА КАРТКА ====
async def show_contracts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message
    rows = await database.fetch_all(sqlalchemy.select(Contract))
    if not rows:
        await msg.reply_text("Договори ще не створені.", reply_markup=contracts_menu)
        return
    companies = {}
    comp_ids = {r["company_id"] for r in rows}
    if comp_ids:
        comps = await database.fetch_all(sqlalchemy.select(Company).where(Company.c.id.in_(comp_ids)))
        companies = {c["id"]: c for c in comps}
    for r in rows:
        comp = companies.get(r["company_id"])
        cname = comp["short_name"] or comp["full_name"] if comp else "—"
        btn = InlineKeyboardButton("Картка", callback_data=f"contract_card:{r['id']}")
        await msg.reply_text(
            f"{r['id']}. {r['number']} — {cname}",
            reply_markup=InlineKeyboardMarkup([[btn]]),
        )


async def contract_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return
    company = await database.fetch_one(sqlalchemy.select(Company).where(Company.c.id == contract["company_id"]))
    lands = await database.fetch_all(
        sqlalchemy.select(LandPlot).join(ContractLandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id).where(
            ContractLandPlot.c.contract_id == contract_id
        )
    )
    land_ids = [l["id"] for l in lands]
    owners = await database.fetch_all(
        sqlalchemy.select(LandPlotOwner).where(LandPlotOwner.c.land_plot_id.in_(land_ids))
    )
    owners_map = {}
    for o in owners:
        owners_map.setdefault(o["land_plot_id"], []).append(o)
    text = (
        f"<b>Договір {contract['number']}</b>\n"
        f"ТОВ: {company['short_name'] or company['full_name']}\n"
        f"Підписано: {contract['date_signed'].date()}\n"
        f"Діє з {contract['date_valid_from'].date()} по {contract['date_valid_to'].date()}\n"
        f"Строк: {contract['duration_years']} років\n\n"
        "<b>Ділянки:</b>"
    )
    for l in lands:
        text += f"\n- {l['cadaster']}"
        olist = owners_map.get(l["id"], [])
        for o in olist:
            payer = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == o["payer_id"]))
            if payer:
                share = o["share"]
                text += f"\n   • {payer['name']} — {share:.2f}"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ До списку", callback_data="to_contracts")]]), parse_mode="HTML")


async def to_contracts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_contracts(update, context)
