import os
import unicodedata
import re
from datetime import datetime, timedelta
from typing import Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile,
)
from telegram.error import BadRequest
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
    UploadedDocs,
)
from keyboards.menu import contracts_menu
from dialogs.post_creation import prompt_add_docs
from ftp_utils import download_file_ftp, delete_file_ftp
from contract_pdf import generate_contract, format_area, format_money, format_share
from template_utils import analyze_template, build_unresolved_message
import sqlalchemy

CHOOSE_COMPANY, SET_DURATION, SET_VALID_FROM, CHOOSE_PAYER, INPUT_LANDS, SET_RENT, SEARCH_LAND = range(7)

BACK_BTN = "◀️ Назад"  # ◀️ Назад
CANCEL_BTN = "❌ Скасувати"  # ❌ Скасувати

# Callback data for navigation buttons
BACK_CB = "contract_back"
CANCEL_CB = "contract_cancel"

# Inline keyboards for navigation
cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton(CANCEL_BTN, callback_data=CANCEL_CB)]])
back_cancel_kb = InlineKeyboardMarkup([
    [InlineKeyboardButton(BACK_BTN, callback_data=BACK_CB),
     InlineKeyboardButton(CANCEL_BTN, callback_data=CANCEL_CB)]
])


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
    query = update.callback_query
    text = update.message.text if update.message else None
    if query:
        await query.answer()
        if query.data == CANCEL_CB:
            await query.message.reply_text(
                "⚠️ Створення договору скасовано. Дані не збережено.",
                reply_markup=contracts_menu,
            )
            context.user_data.clear()
            return ConversationHandler.END
        if query.data == BACK_CB:
            return step_back
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


async def contract_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler for inline back button."""
    query = update.callback_query
    await query.answer()
    state = context.user_data.get("current_state")
    if state == SET_DURATION:
        # Back to company selection
        companies = await database.fetch_all(sqlalchemy.select(Company))
        if not companies:
            await query.message.reply_text("Спочатку додайте хоча б одне ТОВ!", reply_markup=contracts_menu)
            context.user_data.clear()
            return ConversationHandler.END
        kb = ReplyKeyboardMarkup(
            [[f"{c['id']}: {c['short_name'] or c['full_name']}"] for c in companies] + [[CANCEL_BTN]],
            resize_keyboard=True,
        )
        context.user_data["companies"] = {f"{c['id']}: {c['short_name'] or c['full_name']}": c["id"] for c in companies}
        await query.message.reply_text("Оберіть ТОВ-орендаря:", reply_markup=kb)
        await query.message.reply_text("⬇️ Навігація", reply_markup=cancel_kb)
        context.user_data["current_state"] = CHOOSE_COMPANY
        return CHOOSE_COMPANY
    if state == SET_VALID_FROM:
        # Re-prompt duration step
        number = context.user_data.get("contract_number", "")
        await query.message.reply_text(
            f"Номер договору: <b>{number}</b>\nВведіть строк дії в роках:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
        )
        await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = SET_DURATION
        return SET_DURATION
    if state == CHOOSE_PAYER:
        # Back to valid_from
        kb = ReplyKeyboardMarkup(
            [["Від сьогодні"], ["З 1 січня наступного року"], [BACK_BTN, CANCEL_BTN]],
            resize_keyboard=True,
        )
        await query.message.reply_text("Дата набрання чинності:", reply_markup=kb)
        await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = SET_VALID_FROM
        return SET_VALID_FROM
    if state == INPUT_LANDS:
        # Back to choose payer
        payers = await database.fetch_all(
            sqlalchemy.select(Payer).order_by(Payer.c.id.desc()).limit(3)
        )
        kb = ReplyKeyboardMarkup(
            [[f"{p['id']}: {p['name']}"] for p in payers]
            + [["🔍 Пошук пайовика"], ["➕ Створити пайовика"], [BACK_BTN, CANCEL_BTN]],
            resize_keyboard=True,
        )
        context.user_data["recent_payers"] = {f"{p['id']}: {p['name']}": p["id"] for p in payers}
        await query.message.reply_text("Оберіть пайовика:", reply_markup=kb)
        await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = CHOOSE_PAYER
        return CHOOSE_PAYER
    if state == SEARCH_LAND:
        # Back to input lands
        payer_id = context.user_data.get("payer_id")
        lands = await database.fetch_all(
            sqlalchemy.select(LandPlot)
            .join(LandPlotOwner, LandPlot.c.id == LandPlotOwner.c.land_plot_id)
            .where(LandPlotOwner.c.payer_id == payer_id)
        )
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
        await query.message.reply_text(msg, reply_markup=kb)
        await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = INPUT_LANDS
        return INPUT_LANDS
    if state == SET_RENT:
        payer_id = context.user_data.get("payer_id")
        lands = await database.fetch_all(
            sqlalchemy.select(LandPlot)
            .join(LandPlotOwner, LandPlot.c.id == LandPlotOwner.c.land_plot_id)
            .where(LandPlotOwner.c.payer_id == payer_id)
        )
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
        await query.message.reply_text(msg, reply_markup=kb)
        await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = INPUT_LANDS
        return INPUT_LANDS
    return step_back


async def contract_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel contract creation via inline button."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "⚠️ Створення договору скасовано. Дані не збережено.",
        reply_markup=contracts_menu,
    )
    context.user_data.clear()
    return ConversationHandler.END


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
        await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = INPUT_LANDS
        return INPUT_LANDS
    btn = InlineKeyboardButton("➕ Додати до договору", callback_data=f"add_land_to_contract:{row['id']}")
    await update.message.reply_text(
        f"ID {row['id']}: {row['cadaster']} — {row['area']:.4f} га",
        reply_markup=InlineKeyboardMarkup([[btn]]),
    )
    await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = INPUT_LANDS
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
    await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = INPUT_LANDS
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
    await update.message.reply_text("⬇️ Навігація", reply_markup=cancel_kb)
    context.user_data["current_state"] = CHOOSE_COMPANY
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
    await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = SET_DURATION
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
    await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = SET_VALID_FROM
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
    await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = CHOOSE_PAYER
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
        sqlalchemy.select(LandPlot)
        .join(LandPlotOwner, LandPlot.c.id == LandPlotOwner.c.land_plot_id)
        .where(LandPlotOwner.c.payer_id == payer_id)
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
    await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = INPUT_LANDS
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
        await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = SEARCH_LAND
        return SEARCH_LAND
    if text == "✅ Завершити":
        land_ids = context.user_data.get("land_ids", [])
        if not land_ids:
            await update.message.reply_text("Не додано жодної ділянки.")
            return INPUT_LANDS
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
        await update.message.reply_text(
            "Введіть суму орендної плати (грн):",
            reply_markup=ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
        )
        await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = SET_RENT
        return SET_RENT
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
        await update.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
        context.user_data["current_state"] = INPUT_LANDS
        return INPUT_LANDS
        
    # Should not reach here

async def set_rent_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await back_or_cancel(update, context, INPUT_LANDS)
    if result is not None:
        return result
    text = update.message.text.replace(',', '.').strip()
    try:
        rent = float(text)
    except ValueError:
        await update.message.reply_text("Введіть числове значення:")
        return SET_RENT
    context.user_data["rent_amount"] = rent
    land_ids = context.user_data.get("land_ids", [])
    now = datetime.utcnow()
    contract_id = await database.execute(
        Contract.insert().values(
            company_id=context.user_data["company_id"],
            payer_id=context.user_data["payer_id"],
            number=context.user_data["contract_number"],
            date_signed=now,
            date_valid_from=context.user_data["valid_from"],
            date_valid_to=context.user_data["valid_to"],
            duration_years=context.user_data["duration"],
            rent_amount=rent,
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
        CHOOSE_COMPANY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, choose_company),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        SET_DURATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_duration),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        SET_VALID_FROM: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_valid_from),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        CHOOSE_PAYER: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, choose_payer),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        INPUT_LANDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_contract),
            CallbackQueryHandler(add_land_from_search, pattern=r"^add_land_to_contract:\d+$"),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        SET_RENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_rent_amount),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        SEARCH_LAND: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_land),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
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
    buttons = [
        [InlineKeyboardButton("✏️ Редагувати договір", callback_data=f"edit_contract:{contract_id}")],
        [InlineKeyboardButton("📤 Згенерувати PDF", callback_data=f"generate_contract_pdf:{contract_id}")],
        [InlineKeyboardButton("📎 Документи", callback_data=f"contract_docs:{contract_id}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_contract:{contract_id}")],
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_contracts")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def to_contracts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_contracts(update, context)


# ==== ДОКУМЕНТИ ДОГОВОРУ ====
async def contract_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs).where(
            (UploadedDocs.c.entity_type == "contract") &
            (UploadedDocs.c.entity_id == contract_id)
        )
    )
    keyboard = [
        [InlineKeyboardButton("📷 Додати документ", callback_data=f"add_docs:contract:{contract_id}")]
    ]
    for d in docs:
        keyboard.append([
            InlineKeyboardButton(f"⬇️ {d['doc_type']}", callback_data=f"send_pdf:{d['id']}"),
            InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_pdf_db:{d['id']}")
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"contract_card:{contract_id}")])
    text = "📎 Документи договору:" if docs else "Документи відсутні."
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ==== ВИДАЛЕННЯ ДОГОВОРУ ====
async def delete_contract_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    from db import get_user_by_tg_id
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return
    text = (
        f"Ви точно хочете видалити договір <b>{contract['number']}</b>?\n"
        "Цю дію не можна скасувати."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_delete_contract:{contract_id}")],
        [InlineKeyboardButton("❌ Скасувати", callback_data=f"contract_card:{contract_id}")],
    ])
    try:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except BadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def delete_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    from db import get_user_by_tg_id, log_delete
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs).where(
            (UploadedDocs.c.entity_type == "contract") &
            (UploadedDocs.c.entity_id == contract_id)
        )
    )
    for d in docs:
        try:
            delete_file_ftp(d["remote_path"])
        except Exception:
            pass
    if docs:
        await database.execute(UploadedDocs.delete().where(UploadedDocs.c.id.in_([d["id"] for d in docs])))
    await database.execute(ContractLandPlot.delete().where(ContractLandPlot.c.contract_id == contract_id))
    await database.execute(Contract.delete().where(Contract.c.id == contract_id))
    linked = f"docs:{len(docs)}" if docs else ""
    await log_delete(update.effective_user.id, user["role"], "contract", contract_id, contract["number"], linked)
    await query.message.edit_text("✅ Обʼєкт успішно видалено")


# ==== ГЕНЕРАЦІЯ PDF ДОГОВОРУ ====
async def generate_contract_pdf_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return
    if not contract["company_id"]:
        await query.answer("⚠️ У договорі не вказано ТОВ. Неможливо підставити дані.", show_alert=True)
        return
    company = await database.fetch_one(sqlalchemy.select(Company).where(Company.c.id == contract["company_id"]))
    if not company:
        await query.answer("⚠️ У договорі не вказано ТОВ. Неможливо підставити дані.", show_alert=True)
        return
    if not contract["payer_id"]:
        await query.answer("⚠️ У договорі не вказано пайовика. Неможливо підставити дані.", show_alert=True)
        return
    payer = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == contract["payer_id"]))
    if not payer:
        await query.answer("⚠️ У договорі не вказано пайовика. Неможливо підставити дані.", show_alert=True)
        return
    lands = await database.fetch_all(
        sqlalchemy.select(LandPlot)
        .join(ContractLandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .where(ContractLandPlot.c.contract_id == contract_id)
    )
    if not lands:
        await query.answer("⚠️ У договорі не вказано ділянки. Неможливо підставити дані.", show_alert=True)
        return
    land_ids = [l["id"] for l in lands]
    owners_rows = await database.fetch_all(
        sqlalchemy.select(LandPlotOwner.c.land_plot_id, LandPlotOwner.c.payer_id, LandPlotOwner.c.share, Payer.c.name)
        .join(Payer, Payer.c.id == LandPlotOwner.c.payer_id)
        .where(LandPlotOwner.c.land_plot_id.in_(land_ids))
    )
    land_owner_map: dict[int, dict[int, float]] = {}
    payer_shares: dict[int, dict[str, Any]] = {}
    for r in owners_rows:
        land_owner_map.setdefault(r["land_plot_id"], {})[r["payer_id"]] = r["share"]
        info = payer_shares.setdefault(r["payer_id"], {"name": r["name"], "share": 0.0})
        info["share"] += float(r["share"])
    payer_share_value = payer_shares.get(contract["payer_id"], {}).get("share")
    payers_list = "\n".join(
        f"{info['name']} — {format_share(info['share'])}" for info in payer_shares.values()
    )
    plots_table = "\n".join(
        f"{l['cadaster']} — {format_area(l['area'])}" for l in lands
    )
    first_land = lands[0]
    first_land_share = land_owner_map.get(first_land["id"], {}).get(contract["payer_id"])
    from db import get_agreement_templates
    templates = await get_agreement_templates(True)
    if not templates:
        await query.message.edit_text(
            "⚠️ Неможливо згенерувати PDF. Перевірте шаблон або дані договору.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"contract_card:{contract_id}")]])
        )
        return
    template = templates[0]
    tmp_doc = f"temp_docs/template_{contract_id}.docx"
    try:
        download_file_ftp(template["file_path"], tmp_doc)
    except Exception:
        await query.message.edit_text(
            "⚠️ Неможливо згенерувати PDF. Перевірте шаблон або дані договору.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"contract_card:{contract_id}")]])
        )
        return
    variables = {
        "contract_number": contract["number"],
        "contract_date_signed": contract["date_signed"].strftime("%d.%m.%Y"),
        "contract_date_from": contract["date_valid_from"].strftime("%d.%m.%Y"),
        "contract_date_to": contract["date_valid_to"].strftime("%d.%m.%Y"),
        "contract_term": contract["duration_years"],
        "contract_rent": float(contract["rent_amount"]),
        "company_name": company["full_name"],
        "company_code": company["edrpou"],
        "company_address": company["address_legal"],
        "company_director": company["director"],
        "payer_name": payer["name"],
        "payer_tax_id": payer["ipn"],
        "payer_birthdate": payer["birth_date"],
        "payer_passport": f"{(payer['passport_series'] or payer['id_number'] or '')} {payer['passport_number'] or ''} {payer['passport_issuer'] or payer['idcard_issuer'] or ''} {payer['passport_date'] or payer['idcard_date'] or ''}".strip(),
        "payer_address": f"{payer['oblast']} обл., {payer['rayon']} р-н, с. {payer['selo']}, вул. {payer['vul']}, буд. {payer['bud']}{(', кв. ' + payer['kv']) if payer['kv'] else ''}",
        "payer_share": format_share(payer_share_value),
        "payer_phone": payer["phone"],
        "payer_bank_card": payer["bank_card"],
        "payers_list": payers_list,
        "plot_cadastre": first_land["cadaster"],
        "plot_area": format_area(first_land["area"]),
        "plot_share": format_share(first_land_share),
        "plot_ngo": format_money(first_land["ngo"]),
        "plot_location": ", ".join(filter(None, [first_land["council"], first_land["district"], first_land["region"]])),
        "plots_table": plots_table,
        "today": datetime.utcnow().strftime("%d.%m.%Y"),
        "year": datetime.utcnow().year,
    }
    missing, unsupported, total, filled, _ = analyze_template(tmp_doc, variables)
    msg = build_unresolved_message(
        missing,
        unsupported,
        total,
        filled=filled,
        template_name=os.path.basename(template["file_path"]),
    )
    if missing:
        await query.message.reply_text(
            "⚠️ Частина змінних не була заповнена, у шаблон підставлено порожні рядки\nPDF сформовано успішно"
        )
    elif msg:
        await query.message.reply_text(msg)
    try:
        remote_path = generate_contract(
            tmp_doc,
            variables,
            payer_name=payer["name"],
            contract_number=contract["number"],
            year=datetime.utcnow().year,
        )
        os.remove(tmp_doc)
    except Exception:
        if os.path.exists(tmp_doc):
            os.remove(tmp_doc)
        await query.message.edit_text(
            "⚠️ Неможливо згенерувати PDF. Перевірте шаблон або дані договору.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"contract_card:{contract_id}")]])
        )
        return
    await database.execute(
        UploadedDocs.delete().where(
            (UploadedDocs.c.entity_type == "contract") &
            (UploadedDocs.c.entity_id == contract_id) &
            (UploadedDocs.c.doc_type == "generated")
        )
    )
    doc_id = await database.execute(
        UploadedDocs.insert().values(
            entity_type="contract",
            entity_id=contract_id,
            doc_type="generated",
            remote_path=remote_path,
        )
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 Завантажити PDF", callback_data=f"send_pdf:{doc_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"contract_card:{contract_id}")],
    ])
    await query.message.edit_text(
        f"✅ Договір згенеровано\n📐 Шаблон: {os.path.basename(template['file_path'])}\n"
        f"📆 Діє з {contract['date_valid_from'].date()} по {contract['date_valid_to'].date()}",
        reply_markup=keyboard,
    )


# ==== РЕДАГУВАННЯ ДОГОВОРУ (спрощене) ====
EDIT_SIGNED, EDIT_DURATION, EDIT_START, EDIT_RENT, EDIT_LANDS = range(5)


async def edit_contract_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return ConversationHandler.END
    context.user_data["edit_contract_id"] = contract_id
    context.user_data["contract_old"] = contract
    await query.message.edit_text(
        f"Поточна дата підписання: {contract['date_signed'].date()}\nВведіть нову дату (ДД.ММ.РРРР) або '-' щоб залишити без змін:")
    return EDIT_SIGNED


async def edit_contract_signed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    contract = context.user_data["contract_old"]
    if text != "-":
        try:
            dt = datetime.strptime(text, "%d.%m.%Y")
            context.user_data["new_signed"] = dt
        except ValueError:
            await update.message.reply_text("Введіть дату у форматі ДД.ММ.РРРР або '-'")
            return EDIT_SIGNED
    else:
        context.user_data["new_signed"] = contract["date_signed"]
    await update.message.reply_text(
        f"Поточний строк дії: {contract['duration_years']} років. Введіть новий термін або '-' щоб не змінювати:")
    return EDIT_DURATION


async def edit_contract_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    contract = context.user_data["contract_old"]
    if text != "-":
        try:
            years = int(text)
            if years <= 0:
                raise ValueError
            context.user_data["new_duration"] = years
        except ValueError:
            await update.message.reply_text("Введіть ціле число або '-'")
            return EDIT_DURATION
    else:
        context.user_data["new_duration"] = contract["duration_years"]
    await update.message.reply_text(
        f"Поточна дата початку: {contract['date_valid_from'].date()}\nВведіть нову дату (ДД.ММ.РРРР) або '-' щоб не змінювати:")
    return EDIT_START


async def edit_contract_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    contract = context.user_data["contract_old"]
    if text != "-":
        try:
            dt = datetime.strptime(text, "%d.%m.%Y")
            context.user_data["new_start"] = dt
        except ValueError:
            await update.message.reply_text("Введіть дату у форматі ДД.ММ.РРРР або '-'")
            return EDIT_START
    else:
        context.user_data["new_start"] = contract["date_valid_from"]
    await update.message.reply_text(
        f"Поточна сума оренди: {contract['rent_amount']}\nВведіть нову суму або '-' щоб не змінювати:")
    return EDIT_RENT


async def edit_contract_rent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(',', '.').strip()
    contract = context.user_data["contract_old"]
    if text != "-":
        try:
            rent = float(text)
            context.user_data["new_rent"] = rent
        except ValueError:
            await update.message.reply_text("Введіть числове значення або '-'")
            return EDIT_RENT
    else:
        context.user_data["new_rent"] = float(contract["rent_amount"])
    rows = await database.fetch_all(
        sqlalchemy.select(ContractLandPlot.c.land_plot_id).where(ContractLandPlot.c.contract_id == context.user_data["edit_contract_id"])
    )
    current_ids = " ".join(str(r["land_plot_id"]) for r in rows)
    await update.message.reply_text(
        f"Поточні ділянки: {current_ids}\nВведіть список ID через пробіл або '-' щоб не змінювати:")
    return EDIT_LANDS


async def edit_contract_lands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    contract_id = context.user_data["edit_contract_id"]
    if text != "-":
        try:
            land_ids = [int(i) for i in text.replace(',', ' ').split() if i]
        except ValueError:
            await update.message.reply_text("Введіть ID через пробіл або '-'")
            return EDIT_LANDS
    else:
        rows = await database.fetch_all(
            sqlalchemy.select(ContractLandPlot.c.land_plot_id).where(ContractLandPlot.c.contract_id == contract_id)
        )
        land_ids = [r["land_plot_id"] for r in rows]
    new_signed = context.user_data["new_signed"]
    new_start = context.user_data["new_start"]
    new_duration = context.user_data["new_duration"]
    new_end = new_start + timedelta(days=365 * new_duration)
    new_rent = context.user_data["new_rent"]
    await database.execute(
        Contract.update()
        .where(Contract.c.id == contract_id)
        .values(
            date_signed=new_signed,
            date_valid_from=new_start,
            date_valid_to=new_end,
            duration_years=new_duration,
            rent_amount=new_rent,
            updated_at=datetime.utcnow(),
        )
    )
    await database.execute(ContractLandPlot.delete().where(ContractLandPlot.c.contract_id == contract_id))
    for lid in land_ids:
        await database.execute(ContractLandPlot.insert().values(contract_id=contract_id, land_plot_id=lid))
    context.user_data.clear()
    await update.message.reply_text("✅ Зміни збережено", reply_markup=contracts_menu)
    return ConversationHandler.END


edit_contract_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_contract_start, pattern=r"^edit_contract:\d+$")],
    states={
        EDIT_SIGNED: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contract_signed)],
        EDIT_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contract_duration)],
        EDIT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contract_start_date)],
        EDIT_RENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contract_rent)],
        EDIT_LANDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contract_lands)],
    },
    fallbacks=[],
)
