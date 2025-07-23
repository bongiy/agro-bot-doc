from telegram import ReplyKeyboardMarkup

main_menu = ReplyKeyboardMarkup(
    [
        ["🔹 Пайовики", "🔹 Ділянки"],
        ["🔹 Поля", "🔹 Договори"],
        ["🔹 Виплати", "🔹 Звіти"],
        ["🔹 Пошук", "🔄 Перезавантажити"]
    ],
    resize_keyboard=True
)

# Меню для пайовиків (як приклад)
payers_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати пайовика"],
        ["📋 Список пайовиків"],
        ["🔍 Пошук пайовика"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)
