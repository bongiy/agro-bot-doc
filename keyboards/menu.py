from telegram import ReplyKeyboardMarkup

# --- Головне меню ---
main_menu = ReplyKeyboardMarkup(
    [
        ["🔹 Пайовики", "🔹 Ділянки"],
        ["🔹 Поля", "🔹 Договори"],
        ["🔹 Виплати", "🔹 Звіти"],
        ["🔹 Пошук", "🔄 Перезавантажити"]
    ],
    resize_keyboard=True
)

# --- Меню пайовиків ---
payers_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати пайовика"],
        ["📋 Список пайовиків"],
        ["🔍 Пошук пайовика"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню ділянок ---
lands_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати ділянку"],
        ["📋 Список ділянок"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню полів ---
fields_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати поле"],
        ["📋 Список полів"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню договорів ---
contracts_menu = ReplyKeyboardMarkup(
    [
        ["➕ Створити договір"],
        ["📋 Список договорів"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню виплат ---
payments_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати виплату"],
        ["📋 Перелік виплат"],
        ["💳 Звіти по виплатах"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню звітів ---
reports_menu = ReplyKeyboardMarkup(
    [
        ["📊 Зведення по орендній платі"],
        ["📈 Статистика по полях"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню пошуку ---
search_menu = ReplyKeyboardMarkup(
    [
        ["🔎 Пошук пайовика"],
        ["🔎 Пошук ділянки"],
        ["🔎 Пошук договору"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)
