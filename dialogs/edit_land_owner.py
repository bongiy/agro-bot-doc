from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from db import database, LandPlot, Payer
import sqlalchemy

ASK_OWNER_SEARCH, ASK_OWNER_SELECT = range(2)

async def start_edit_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    context.user_data["edit_land_id"] = land_id
    await query.message.edit_text(
        "Введіть ІПН, ПІБ, телефон або ID пайовика для пошуку власника ділянки:"
    )
    return ASK_OWNER_SEARCH

async def search_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    res = []
    found_ids = set()
    # Аналог пошуку пайовика!
    if len(q) == 10 and q.isdigit():
        temp = await database.fetch_all(Payer.select().where(Payer.c.ipn == q))
        res.extend([r for r in temp if r.id not in found_ids])
        found_ids.update([r.id for r in temp])
    if (q.startswith("+380") and len(q) == 13) or (q.startswith("0") and len(q) == 10):
        phone = q if q.startswith("+") else "+38" + q
        temp = await database.fetch_all(Payer.select().where(Payer.c.phone == phone))
        res.extend([r for r in temp if r.id not in found_ids])
        found_ids.update([r.id for r in temp])
    if q.isdigit():
        q_int = int(q)
        temp = await database.fetch_all(Payer.select().where(Payer.c.id == q_int))
        res.extend([r for r in temp if r.id not in found_ids])
        found_ids.update([r.id for r in temp])
    temp = await database.fetch_all(Payer.select().where(Payer.c.name.ilike(f"%{q}%")))
    res.extend([r for r in temp if r.id not in found_ids])
    found_ids.update([r.id for r in temp])

    if not res:
        await update.message.reply_text("Пайовика не знайдено.")
        return ASK_OWNER_SEARCH

    keyboard = [
        [InlineKeyboardButton(f"{r.name} (ІПН: {r.ipn})", callback_data=f"select_owner:{r.id}")]
        for r in res
    ]
    await update.message.reply_text("Оберіть власника:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_OWNER_SELECT

async def select_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    land_id = context.user_data.get("edit_land_id")
    await database.execute(
        LandPlot.update().where(LandPlot.c.id == land_id).values(payer_id=payer_id)
    )
    await query.answer("Власника оновлено!")
    await query.message.edit_text("Власника ділянки оновлено.")
    return ConversationHandler.END

edit_land_owner_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_owner, pattern=r"^edit_land_owner:\d+$")],
    states={
        ASK_OWNER_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_owner)],
        ASK_OWNER_SELECT: [CallbackQueryHandler(select_owner, pattern=r"^select_owner:\d+$")],
    },
    fallbacks=[]
)
