from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes


async def prompt_add_docs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    entity_type: str,
    entity_id: int,
    final_text: str,
    final_markup,
):
    """Ask user to upload documents right after object creation."""

    context.user_data["post_create_msg"] = final_text
    context.user_data["post_create_markup"] = final_markup

    await update.message.reply_text(
        "✅ Об’єкт створено.\n📎 Бажаєте одразу додати документи?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Додати зараз",
                        callback_data=f"add_docs:{entity_type}:{entity_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Пропустити",
                        callback_data=f"skip_docs:{entity_type}:{entity_id}",
                    )
                ],
            ]
        ),
    )


async def skip_add_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to the stored message when user skips document upload."""

    query = update.callback_query
    await query.answer()

    text = context.user_data.pop("post_create_msg", "")
    markup = context.user_data.pop("post_create_markup", None)

    if isinstance(markup, ReplyKeyboardMarkup):
        await query.message.delete()
        await query.message.reply_text(text, reply_markup=markup)
    else:
        await query.message.edit_text(text, reply_markup=markup)

    context.user_data.clear()

