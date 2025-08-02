import os
import unicodedata
import re
from datetime import datetime, timedelta
from typing import Any
import logging
import html

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
    AgreementTemplate,
    LandPlot,
    LandPlotOwner,
    Payer,
    UploadedDocs,
    Payment,
    PayerContract,
)
from keyboards.menu import contracts_menu
from dialogs.post_creation import prompt_add_docs
from ftp_utils import download_file_ftp, delete_file_ftp
from contract_generation_v2 import (
    generate_contract_v2,
    format_area,
    format_money,
    format_share,
)
from template_utils import analyze_template, build_unresolved_message
import sqlalchemy

logger = logging.getLogger(__name__)

status_values = {
    "signed": "🟡 Підписаний",
    "sent_for_registration": "🟠 Відправлено на реєстрацію",
    "returned_for_correction": "🔴 Повернуто з реєстрації на доопрацювання",
    "registered": "🟢 Зареєстровано в ДРРП",
}

payment_type_short = {
    "cash": "💸",
    "card": "💳",
    "bank": "🏦",
}

CHOOSE_COMPANY, SET_DURATION, SET_VALID_FROM, CHOOSE_PAYER, INPUT_LANDS, SET_RENT = range(6)

BACK_BTN = "◀️ Назад"  # ◀️ Назад
CANCEL_BTN = "❌ Скасувати"  # ❌ Скасувати

# Callback data for navigation buttons
BACK_CB = "contract_back"
CANCEL_CB = "contract_cancel"
ADD_PLOT_PREFIX = "add_plot"
FINISH_PLOT_SELECTION_CB = "finish_plot_selection"

# Inline keyboards for navigation
cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton(CANCEL_BTN, callback_data=CANCEL_CB)]])
back_cancel_kb = InlineKeyboardMarkup([
    [InlineKeyboardButton(BACK_BTN, callback_data=BACK_CB),
     InlineKeyboardButton(CANCEL_BTN, callback_data=CANCEL_CB)]
])


async def build_land_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """Return keyboard with land plots for the current payer."""
    payer_id = context.user_data.get("payer_id")
    selected = set(context.user_data.get("land_ids", []))
    rows = await database.fetch_all(
        sqlalchemy.select(LandPlot)
        .join(LandPlotOwner, LandPlot.c.id == LandPlotOwner.c.land_plot_id)
        .where(LandPlotOwner.c.payer_id == payer_id)
    )
    keyboard = [
        [InlineKeyboardButton(
            f"\U0001F4CD {r['cadaster']} — {r['area']:.4f} га",
            callback_data=f"{ADD_PLOT_PREFIX}:{r['id']}"
        )]
        for r in rows if r["id"] not in selected
    ]
    keyboard.append([InlineKeyboardButton("✅ Завершити вибір", callback_data=FINISH_PLOT_SELECTION_CB)])
    keyboard.append([InlineKeyboardButton(BACK_BTN, callback_data=BACK_CB)])
    return InlineKeyboardMarkup(keyboard)


async def show_land_options(msg_obj: Any, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = await build_land_keyboard(context)
    text = "Оберіть ділянки для договору:"
    if getattr(getattr(msg_obj, "from_user", None), "is_bot", False):
        await msg_obj.edit_text(text, reply_markup=markup)
    else:
        await msg_obj.reply_text(text, reply_markup=markup)
    context.user_data["current_state"] = INPUT_LANDS
    return INPUT_LANDS


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
    if state == SET_RENT:
        return await show_land_options(query.message, context)
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


async def add_plot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add land plot to contract from inline keyboard."""
    query = update.callback_query
    plot_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == plot_id))
    if not row:
        await query.answer("Ділянку не знайдено", show_alert=True)
        return INPUT_LANDS
    context.user_data.setdefault("land_ids", []).append(plot_id)
    await query.answer()
    text = f"✅ Додано: {row['cadaster']}\n➕ Оберіть ще або натисніть \"✅ Завершити вибір\""
    markup = await build_land_keyboard(context)
    await query.message.edit_text(text, reply_markup=markup)
    return INPUT_LANDS


async def finish_plot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish choosing plots and proceed to rent input."""
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("land_ids"):
        await query.answer("Не обрано жодної ділянки", show_alert=True)
        return INPUT_LANDS
    invalid = []
    for lid in context.user_data.get("land_ids", []):
        total = await database.fetch_val(
            sqlalchemy.select(sqlalchemy.func.sum(LandPlotOwner.c.share)).where(
                LandPlotOwner.c.land_plot_id == lid
            )
        )
        if total is None or abs(total - 1.0) > 0.01:
            invalid.append(lid)
    if invalid:
        markup = await build_land_keyboard(context)
        await query.message.edit_text(
            f"⚠️ Не охоплено 100% частки по ділянках: {', '.join(map(str, invalid))}",
            reply_markup=markup,
        )
        context.user_data["current_state"] = INPUT_LANDS
        return INPUT_LANDS
    await query.message.edit_text("✅ Ділянки додано")
    await query.message.reply_text(
        "Введіть суму орендної плати (грн):",
        reply_markup=ReplyKeyboardMarkup([[BACK_BTN, CANCEL_BTN]], resize_keyboard=True),
    )
    await query.message.reply_text("⬇️ Навігація", reply_markup=back_cancel_kb)
    context.user_data["current_state"] = SET_RENT
    return SET_RENT


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

    context.user_data["land_ids"] = []
    await show_land_options(update.message, context)
    return INPUT_LANDS


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
            status="signed",
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
            CallbackQueryHandler(add_plot, pattern=rf"^{ADD_PLOT_PREFIX}:\d+$"),
            CallbackQueryHandler(finish_plot_selection, pattern=f"^{FINISH_PLOT_SELECTION_CB}$"),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        SET_RENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_rent_amount),
            CallbackQueryHandler(contract_back, pattern=f"^{BACK_CB}$"),
            CallbackQueryHandler(contract_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
    },
    fallbacks=[],
)


# ==== СПИСОК ТА КАРТКА ====
async def show_contracts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message

    payer_name_col = getattr(Payer.c, "full_name", Payer.c.name)

    rows = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.number,
            sqlalchemy.extract("year", Contract.c.date_signed).label("year"),
            Company.c.short_name,
            Company.c.full_name,
            sqlalchemy.func.array_agg(payer_name_col).label("payer_names"),
        )
        .select_from(Contract)
        .join(Company, Company.c.id == Contract.c.company_id)
        .outerjoin(PayerContract, PayerContract.c.contract_id == Contract.c.id)
        .outerjoin(Payer, Payer.c.id == PayerContract.c.payer_id)
        .group_by(
            Contract.c.id,
            Contract.c.number,
            Contract.c.date_signed,
            Company.c.short_name,
            Company.c.full_name,
        )
    )
    if not rows:
        await msg.reply_text("Договори ще не створені.", reply_markup=contracts_menu)
        return
    for r in rows:
        cname = r["short_name"] or r["full_name"] or "—"
        payers = [p for p in (r["payer_names"] or []) if p]
        if not payers:
            payer_line = "👤 Пайовик: —"
        elif len(payers) == 1:
            payer_line = f"👤 Пайовик: {html.escape(payers[0])}"
        else:
            payer_line = f"👤 Пайовик: {html.escape(payers[0])} +{len(payers) - 1} ще"
        btn = InlineKeyboardButton("Картка", callback_data=f"agreement_card:{r['id']}")
        number_part = html.escape(r["number"])
        year_part = f"/{int(r['year'])}" if r["year"] else ""
        text = (
            f"📄 Договір №{number_part}{year_part}\n"
            f"{payer_line}\n"
            f"🏢 Орендар: {html.escape(cname)}"
        )
        await msg.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([[btn]]),
            parse_mode="HTML",
        )


async def agreement_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return
    company = await database.fetch_one(sqlalchemy.select(Company).where(Company.c.id == contract["company_id"]))
    payer = await database.fetch_one(sqlalchemy.select(Payer).where(Payer.c.id == contract["payer_id"]))
    lands = await database.fetch_all(
        sqlalchemy.select(LandPlot).join(ContractLandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id).where(
            ContractLandPlot.c.contract_id == contract_id
        )
    )
    land = lands[0] if lands else None
    docs_count = await database.fetch_val(
        sqlalchemy.select(sqlalchemy.func.count()).select_from(UploadedDocs).where(
            (UploadedDocs.c.entity_type == "contract") & (UploadedDocs.c.entity_id == contract_id)
        )
    )
    tmpl = None
    if contract["template_id"]:
        tmpl = await database.fetch_one(sqlalchemy.select(AgreementTemplate).where(AgreementTemplate.c.id == contract["template_id"]))
    template_name = tmpl["name"] if tmpl else "—"

    status_text = status_values.get(contract["status"], contract["status"] or "-")
    registration_block = ""
    if contract["status"] == "registered":
        reg_date = contract["registration_date"].strftime("%d.%m.%Y") if contract["registration_date"] else "-"
        registration_block = f"\nНомер реєстрації: {contract['registration_number']}\nДата реєстрації: {reg_date}"

    location = "—"
    if land:
        loc_parts = [land["council"], land["district"], land["region"]]
        location = ", ".join([p for p in loc_parts if p]) or "-"
    plot_txt = (
        f"Кадастровий номер: {land['cadaster']}\n"
        f"Площа: {land['area']:.4f} га\n"
        f"НГО: {land['ngo'] if land['ngo'] else '-'} грн\n"
        f"Розташування: {location}"
    ) if land else "-"

    text = (
        f"📄 <b>Договір оренди №{contract['number']}</b>\n"
        f"Підписано: {contract['date_signed'].date()}\n"
        f"Строк дії: {contract['duration_years']} років (до {contract['date_valid_to'].date()})\n\n"
        f"📌 Статус: {status_text}{registration_block}\n\n"
        f"🏢 <b>Орендар (ТОВ)</b>:\n"
        f"{company['short_name'] or company['full_name']}\n"
        f"Код ЄДРПОУ: {company['edrpou']}\n"
        f"Директор: {company['director']}\n\n"
        f"👤 <b>Орендодавець (пайовик)</b>:\n"
        f"{payer['name']}\n"
        f"Паспорт: {payer['passport_series'] or ''} {payer['passport_number'] or ''}\n"
        f"ІПН: {payer['ipn']}\n"
        f"Адреса: {payer['oblast']} обл., {payer['rayon']} р-н, {payer['selo']}, {payer['vul']} {payer['bud']} {payer['kv'] or ''}\n"
        f"Телефон: {payer['phone'] or '-'}\n"
        f"Картка: {payer['bank_card'] or '-'}\n\n"
        f"📍 <b>Ділянка</b>:\n{plot_txt}\n\n"
        f"💰 <b>Орендна плата</b>: {contract['rent_amount']} грн/рік\n\n"
        f"📎 Шаблон: {template_name}\n\n"
        f"📥 Завантажені документи: {docs_count} файла(ів)"
    )

    from crm.events_integration import get_events_text, events_button
    events_block = await get_events_text("contract", contract_id)
    text += "\n\n" + events_block

    # === Платежі ===
    payments = await database.fetch_all(
        sqlalchemy.select(Payment).where(Payment.c.agreement_id == contract_id).order_by(Payment.c.payment_date)
    )
    payments_by_year: dict[int, list] = {}
    for p in payments:
        payments_by_year.setdefault(p["payment_date"].year, []).append(p)
    totals = {y: sum(float(r["amount"]) for r in rows) for y, rows in payments_by_year.items()}
    current_year = datetime.utcnow().year
    curr_total = totals.get(current_year, 0)
    rent = float(contract["rent_amount"] or 0)
    debt = max(0, rent - curr_total)
    paid_full = curr_total >= rent
    history_lines = []
    for p in payments_by_year.get(current_year, []):
        typ = payment_type_short.get(p["payment_type"], "")
        history_lines.append(f"— {p['payment_date'].strftime('%d.%m.%Y')} — {typ} {format_money(p['amount'])}")
    prev_years = ""
    for y in sorted(totals):
        if y == current_year:
            continue
        total = totals[y]
        if total >= rent:
            status = "✅ Виплачено повністю"
        else:
            status = f"❌ Не виплачено (борг: {format_money(rent - total)})"
        prev_years += f"{y} — {status}\n"

    text += (
        f"\n\n📆 <b>Орендна плата</b>: {format_money(rent)}/рік\n\n"
        f"🗓 Поточний рік: {current_year}\n"
        f"✅ Виплачено: {format_money(curr_total)}\n"
        f"🔴 Борг: {format_money(debt)}\n"
        f"📌 Виплачено повністю: {'✅ Так' if paid_full else '❌ Ні'}"
    )
    if history_lines:
        text += "\n\n📅 Історія {year}:\n".format(year=current_year)
        text += "\n".join(history_lines)
    if prev_years:
        text += "\n\n📂 Попередні роки:\n" + prev_years.strip()

    buttons = [
        [InlineKeyboardButton("➕ Додати виплату", callback_data=f"add_payment:{contract_id}")],
        [InlineKeyboardButton("📊 Зведення по роках", callback_data=f"payment_summary:{contract_id}")],
        [InlineKeyboardButton("🗂 Історія виплат за рік", callback_data=f"payment_history:{contract_id}")],
        [InlineKeyboardButton("📄 Згенерувати договір (docx/pdf)", callback_data=f"generate_contract_pdf:{contract_id}")],
        [InlineKeyboardButton("📝 Редагувати", callback_data=f"edit_contract:{contract_id}")],
        [InlineKeyboardButton("📌 Змінити статус", callback_data=f"change_status:{contract_id}")],
        [InlineKeyboardButton("📁 Документи", callback_data=f"contract_docs:{contract_id}")],
        [events_button("contract", contract_id)],
    ]
    from db import get_user_by_tg_id
    user = await get_user_by_tg_id(update.effective_user.id)
    if user and user["role"] == "admin":
        buttons.append([InlineKeyboardButton("🗑 Видалити договір", callback_data=f"agreement_delete:{contract_id}")])
    buttons.append(
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_contracts")]
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

# old name for compatibility
contract_card = agreement_card


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
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")])
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
        [InlineKeyboardButton("❌ Скасувати", callback_data=f"agreement_card:{contract_id}")],
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


async def agreement_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    context.user_data["delete_agreement_id"] = contract_id
    text = (
        f"⚠️ Ви дійсно хочете видалити договір №{contract['number']}?\n\n"
        "Це призведе до:\n"
        "• Видалення запису про договір\n"
        "• Видалення всіх пов'язаних виплат\n"
        "• Видалення файлів договору з FTP (PDF, скани)\n\n"
        "❗ Цю дію неможливо скасувати."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Так, видалити", callback_data="agreement_delete_confirm")],
        [InlineKeyboardButton("⬅️ Скасувати", callback_data=f"agreement_card:{contract_id}")],
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def agreement_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = context.user_data.get("delete_agreement_id")
    from db import get_user_by_tg_id, log_delete
    if not contract_id:
        await query.answer("Невірний запит на видалення.", show_alert=True)
        return
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return
    payments = await database.fetch_all(sqlalchemy.select(Payment).where(Payment.c.agreement_id == contract_id))
    if payments:
        await database.execute(Payment.delete().where(Payment.c.agreement_id == contract_id))
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs).where(
            (UploadedDocs.c.entity_type == "contract") & (UploadedDocs.c.entity_id == contract_id)
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
    info = []
    if payments:
        info.append(f"payments:{len(payments)}")
    if docs:
        info.append(f"docs:{len(docs)}")
    await log_delete(update.effective_user.id, user["role"], "contract", contract_id, contract["number"], ",".join(info))
    context.user_data.pop("delete_agreement_id", None)
    await query.message.edit_text(f"✅ Договір №{contract['number']} успішно видалено.")


# ==== ГЕНЕРАЦІЯ PDF ДОГОВОРУ ====
async def generate_contract_pdf_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    if not contract:
        await query.answer("Договір не знайдено!", show_alert=True)
        return

    try:
        remote_path, gen_log = await generate_contract_v2(contract_id)
    except Exception:
        logger.exception("Failed to generate contract PDF")
        await query.message.edit_text(
            "⚠️ Неможливо згенерувати PDF. Перевірте шаблон або дані договору.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")]]
            ),
        )
        return

    row = await database.fetch_one(
        sqlalchemy.select(UploadedDocs.c.id)
        .where(
            (UploadedDocs.c.entity_type == "contract")
            & (UploadedDocs.c.entity_id == contract_id)
            & (UploadedDocs.c.doc_type == "generated")
        )
        .order_by(UploadedDocs.c.id.desc())
    )
    doc_id = row["id"] if row else None

    from db import get_agreement_templates
    templates = await get_agreement_templates(True)
    template_name = os.path.basename(templates[0]["file_path"]) if templates else ""

    is_pdf = str(remote_path).lower().endswith(".pdf")

    if gen_log:
        await query.message.reply_text(gen_log)

    warn_text = (
        "⚠️ PDF не згенеровано — на сервері відсутні необхідні компоненти.\n"
        "📄 Надаємо договір у форматі DOCX.\n\n"
        if not is_pdf
        else ""
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📎 Завантажити PDF" if is_pdf else "📎 Завантажити DOCX",
                    callback_data=f"send_pdf:{doc_id}",
                )
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")],
        ]
    )

    await query.message.edit_text(
        warn_text
        + f"✅ Договір згенеровано\n📐 Шаблон: {os.path.basename(template_name)}\n"
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


# ==== ЗМІНА СТАТУСУ ДОГОВОРУ ====
CHANGE_STATUS, REG_NUMBER, REG_DATE = range(3)


async def change_status_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    context.user_data["status_contract_id"] = contract_id
    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"select_status:{key}")]
        for key, text in status_values.items()
    ]
    keyboard.append([InlineKeyboardButton("❌ Скасувати", callback_data=f"agreement_card:{contract_id}")])
    await query.message.edit_text("Оберіть новий статус:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHANGE_STATUS


async def select_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    status = query.data.split(":")[1]
    context.user_data["new_status"] = status
    contract_id = context.user_data.get("status_contract_id")
    if status == "registered":
        await query.message.edit_text("Введіть номер реєстрації:")
        return REG_NUMBER
    await database.execute(
        Contract.update()
        .where(Contract.c.id == contract_id)
        .values(status=status, registration_number=None, registration_date=None, updated_at=datetime.utcnow())
    )
    await query.message.edit_text("✅ Статус оновлено", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")]
    ]))
    context.user_data.clear()
    return ConversationHandler.END


async def input_reg_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["registration_number"] = update.message.text.strip()
    await update.message.reply_text("Введіть дату реєстрації (ДД.ММ.РРРР):")
    return REG_DATE


async def input_reg_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        reg_date = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Введіть дату у форматі ДД.ММ.РРРР:")
        return REG_DATE
    contract_id = context.user_data.get("status_contract_id")
    await database.execute(
        Contract.update()
        .where(Contract.c.id == contract_id)
        .values(
            status=context.user_data.get("new_status", "registered"),
            registration_number=context.user_data.get("registration_number"),
            registration_date=reg_date,
            updated_at=datetime.utcnow(),
        )
    )
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Статус оновлено",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")]])
    )
    return ConversationHandler.END


change_status_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(change_status_start, pattern=r"^change_status:\d+$")],
    states={
        CHANGE_STATUS: [CallbackQueryHandler(select_status, pattern=r"^select_status:\w+$")],
        REG_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_reg_number)],
        REG_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_reg_date)],
    },
    fallbacks=[],
)


async def payment_summary_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    contract = await database.fetch_one(sqlalchemy.select(Contract).where(Contract.c.id == contract_id))
    payments = await database.fetch_all(sqlalchemy.select(Payment).where(Payment.c.agreement_id == contract_id))
    by_year: dict[int, float] = {}
    for p in payments:
        y = p["payment_date"].year
        by_year[y] = by_year.get(y, 0) + float(p["amount"])
    rent = float(contract["rent_amount"] or 0)
    lines = []
    for y in sorted(by_year):
        total = by_year[y]
        if total >= rent:
            status = "✅ Виплачено повністю"
        else:
            status = f"❌ Борг: {format_money(rent - total)}"
        lines.append(f"{y}: {format_money(total)} — {status}")
    if not lines:
        lines.append("Немає даних.")
    lines.append("\n⬅️ Назад")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")]])
    await query.message.edit_text("\n".join(lines), reply_markup=kb)


async def payment_history_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    contract_id = int(query.data.split(":")[1])
    year = datetime.utcnow().year
    payments = await database.fetch_all(
        sqlalchemy.select(Payment).where(
            (Payment.c.agreement_id == contract_id)
            & (sqlalchemy.extract("year", Payment.c.payment_date) == year)
        ).order_by(Payment.c.payment_date)
    )
    lines = [f"Виплати {year}:"]
    for p in payments:
        typ = payment_type_short.get(p["payment_type"], "")
        lines.append(f"— {p['payment_date'].strftime('%d.%m.%Y')} — {typ} {format_money(p['amount'])}")
    if len(lines) == 1:
        lines.append("Немає виплат")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"agreement_card:{contract_id}")]])
    await query.message.edit_text("\n".join(lines), reply_markup=kb)
