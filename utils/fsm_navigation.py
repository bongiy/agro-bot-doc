from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, ContextTypes

BACK_BTN = "⬅️ Назад"
CANCEL_BTN = "❌ Скасувати"

back_cancel_keyboard = ReplyKeyboardMarkup(
    [[BACK_BTN, CANCEL_BTN]], resize_keyboard=True
)


def push_state(context: ContextTypes.DEFAULT_TYPE, state: int) -> None:
    """Add state to user's FSM history."""
    history = context.user_data.setdefault("fsm_history", [])
    history.append(state)


def pop_state(context: ContextTypes.DEFAULT_TYPE):
    """Pop current state and return previous one."""
    history = context.user_data.get("fsm_history", [])
    if history:
        history.pop()
    return history[-1] if history else None


def cancel_handler(menu_function):
    """Factory for creating cancel handlers that return to a menu."""

    async def _cancel(update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❌ Додавання події скасовано. Ви повернулись до CRM.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        if menu_function:
            await menu_function(update, context)
        return ConversationHandler.END

    return _cancel


async def handle_back_cancel(update, context: ContextTypes.DEFAULT_TYPE, menu_function=None):
    """Handle navigation buttons for FSM dialogs."""
    text = update.message.text if update.message else None
    if text == CANCEL_BTN:
        await update.message.reply_text(
            "❌ Додавання події скасовано. Ви повернулись до CRM.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        if menu_function:
            await menu_function(update, context)
        return ConversationHandler.END
    if text == BACK_BTN:
        prev_state = pop_state(context)
        if prev_state is None:
            await update.message.reply_text(
                "❌ Додавання події скасовано. Ви повернулись до CRM.",
                reply_markup=ReplyKeyboardRemove(),
            )
            context.user_data.clear()
            if menu_function:
                await menu_function(update, context)
            return ConversationHandler.END
        return prev_state
    return None
