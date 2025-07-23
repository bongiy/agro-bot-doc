from telegram.ext import ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters
from dialogs.payer import to_menu

SEARCH_INPUT = 1001  # Унікальний стан пошуку

async def payer_search_start(update, context):
    await update.message.reply_text("Введіть ID, ІПН, телефон або фрагмент ПІБ для пошуку пайовика:")
    return SEARCH_INPUT

async def payer_search_do(update, context):
    q = update.message.text.strip()
    results = []
    found_ids = set()
    # Далі — розумний пошук (див. попередні мої відповіді, тут не повторюю для економії місця)
    # ... (Пошук по ІПН, телефону, id, фрагменту ПІБ)
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
