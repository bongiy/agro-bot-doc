from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, filters, ContextTypes
from dialogs.payer import to_menu
from db import database, Payer
import re

SEARCH_INPUT = 1001  # Унікальний стан пошуку

async def payer_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ID, ІПН, телефон або фрагмент ПІБ для пошуку пайовика:")
    return SEARCH_INPUT

async def payer_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: payer_search_do start!", flush=True)
    q = update.message.text.strip()
    results = []
    found_ids = set()
    # 1. Якщо ІПН (10 цифр)
    if re.fullmatch(r"\d{10}", q):
        res = await database.fetch_all(Payer.select().where(Payer.c.ipn == q))
        print(f"DEBUG: found {len(res)} records by ipn", flush=True)
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    # 2. Якщо телефон
    if re.fullmatch(r"(\+380|0)\d{9}", q):
        phone = q if q.startswith("+") else "+38" + q
        res = await database.fetch_all(Payer.select().where(Payer.c.phone == phone))
        print(f"DEBUG: found {len(res)} records by phone", flush=True)
        results.extend([r for r in res if r.id not in found_ids])
        found_ids.update([r.id for r in res])
    # 3. Якщо ID (в межах int32)
    if q.isdigit():
        q_int = int(q)
        if -(2**31) <= q_int <= 2**31-1:
            res = await database.fetch_all(Payer.select().where(Payer.c.id == q_int))
            print(f"DEBUG: found {len(res)} records by id", flush=True)
            results.extend([r for r in res if r.id not in found_ids])
            found_ids.update([r.id for r in res])
    # 4. Фрагмент ПІБ (регістр неважливий)
    res = await database.fetch_all(Payer.select().where(Payer.c.name.ilike(f"%{q}%")))
    print(f"DEBUG: found {len(res)} records by name", flush=True)
    results.extend([r for r in res if r.id not in found_ids])
    found_ids.update([r.id for r in res])

    if not results:
        await update.message.reply_text("Пайовика не знайдено.")
        return ConversationHandler.END
    for p in results:
        btn = InlineKeyboardButton(f"Картка", callback_data=f"payer_card:{p.id}")
        await update.message.reply_text(
            f"{p.id}. {p.name} (ІПН: {p.ipn})",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )
    return ConversationHandler.END

search_payer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Пошук пайовика$"), payer_search_start)],
    states={
        SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payer_search_do)],
    },
    fallbacks=[CommandHandler("start", to_menu)],
)
