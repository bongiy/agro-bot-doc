from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from dialogs.payer import to_menu
from db import (
    database,
    Payer,
    LandPlot,
    Contract,
    Company,
    PayerContract,
)
from keyboards.menu import search_menu, contracts_menu
from utils.payers import get_payers_for_contract
from utils.names import format_payers_line
import sqlalchemy
import re
import html


def format_cadaster(text: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if len(digits) != 19:
        return None
    return f"{digits[:10]}:{digits[10:12]}:{digits[12:15]}:{digits[15:]}"

SEARCH_INPUT = 1001  # Унікальний стан пошуку
SEARCH_LAND_INPUT = 1002
SEARCH_CONTRACT_INPUT = 1003

async def payer_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ID, ІПН, телефон або фрагмент ПІБ для пошуку пайовика:")
    return SEARCH_INPUT

async def payer_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    results = []
    found_ids = set()
    # 1. Якщо ІПН (10 цифр)
    if re.fullmatch(r"\d{10}", q):
        res = await database.fetch_all(Payer.select().where(Payer.c.ipn == q))
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    # 2. Якщо телефон
    if re.fullmatch(r"(\+380|0)\d{9}", q):
        phone = q if q.startswith("+") else "+38" + q
        res = await database.fetch_all(Payer.select().where(Payer.c.phone == phone))
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    # 3. Якщо ID (в межах int32)
    if q.isdigit():
        q_int = int(q)
        if -(2**31) <= q_int <= 2**31-1:
            res = await database.fetch_all(Payer.select().where(Payer.c.id == q_int))
            results.extend([r for r in res if r.id not in found_ids])
            found_ids.update([r.id for r in res])
    # 4. Фрагмент ПІБ (регістр неважливий)
    res = await database.fetch_all(Payer.select().where(Payer.c.name.ilike(f"%{q}%")))
    results.extend([r for r in res if r.id not in found_ids])
    found_ids.update([r.id for r in res])

    if not results:
        await update.message.reply_text("Пайовика не знайдено.")
        return ConversationHandler.END
    for p in results:
        status = " ⚰️" if getattr(p, "is_deceased", False) else ""
        btn = InlineKeyboardButton("Картка", callback_data=f"payer_card:{p.id}")
        await update.message.reply_text(
            f"{p.id}. {p.name}{status} (ІПН: {p.ipn})",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )
    return ConversationHandler.END

search_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔍 Пошук пайовика$"), payer_search_start)],
    states={
        SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payer_search_do)],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)


async def land_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть кадастровий номер ділянки:")
    return SEARCH_LAND_INPUT


async def land_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cad = format_cadaster(update.message.text)
    if not cad:
        await update.message.reply_text("Некоректний номер. Спробуйте ще:")
        return SEARCH_LAND_INPUT
    row = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.cadaster == cad))
    if not row:
        await update.message.reply_text("Ділянку не знайдено.")
        return ConversationHandler.END
    btn = InlineKeyboardButton("Картка", callback_data=f"land_card:{row['id']}")
    add_btn = InlineKeyboardButton("➕ Додати до договору", callback_data=f"add_land_to_contract:{row['id']}")
    await update.message.reply_text(
        f"{row['id']}. {row['cadaster']} — {row['area']:.4f} га",
        reply_markup=InlineKeyboardMarkup([[btn, add_btn]]),
    )
    return ConversationHandler.END


search_land_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔍 Пошук ділянки$"), land_search_start)],
    states={
        SEARCH_LAND_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_search_do)],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)


async def contract_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть номер договору або ПІБ пайовика:")
    return SEARCH_CONTRACT_INPUT


async def contract_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    payer_direct = sqlalchemy.alias(Payer, name="payer_direct")
    query = (
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.number,
            Company.c.short_name,
            Company.c.full_name,
        )
        .select_from(Contract)
        .join(Company, Company.c.id == Contract.c.company_id)
        .outerjoin(PayerContract, PayerContract.c.contract_id == Contract.c.id)
        .outerjoin(Payer, Payer.c.id == PayerContract.c.payer_id)
        .outerjoin(payer_direct, payer_direct.c.id == Contract.c.payer_id)
        .where(
            (Contract.c.number.ilike(f"%{q}%"))
            | (Payer.c.name.ilike(f"%{q}%"))
            | (payer_direct.c.name.ilike(f"%{q}%"))
        )
        .distinct()
    )
    rows = await database.fetch_all(query)
    if not rows:
        await update.message.reply_text("❗ Договір не знайдено.")
    else:
        for r in rows:
            cname = html.escape(r["short_name"] or r["full_name"] or "—")
            payers = await get_payers_for_contract(r["id"])
            text = (
                f"📄 Договір №{html.escape(r['number'])}\n"
                f"{format_payers_line(payers)}\n"
                f"🏢 Орендар: {cname}"
            )
            btn = InlineKeyboardButton(
                "Картка", callback_data=f"agreement_card:{r['id']}"
            )
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup([[btn]]), parse_mode="HTML"
            )

    if context.user_data.get("last_menu") == "contracts":
        await update.message.reply_text(
            "Меню «Договори»", reply_markup=contracts_menu
        )
    else:
        await update.message.reply_text(
            "Меню «Пошук»", reply_markup=search_menu
        )
    return ConversationHandler.END


search_contract_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔍 Пошук договору$"), contract_search_start)],
    states={
        SEARCH_CONTRACT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contract_search_do)],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
