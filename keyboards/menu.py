from telegram import ReplyKeyboardMarkup

# --- Головне меню для звичайного користувача ---
main_menu = ReplyKeyboardMarkup(
    [
        ["👤 Пайовики", "🌿 Ділянки"],
        ["🌾 Поля", "📄 Договори"],
        ["💳 Виплати", "📊 Звіти"],
        ["📒 CRM", "🔎 Пошук"],
        ["🛡️ Адмінпанель"]
    ],
    resize_keyboard=True
)

# --- Головне меню для адміністратора ---
main_menu_admin = ReplyKeyboardMarkup(
    [
        ["👤 Пайовики", "🌿 Ділянки"],
        ["🌾 Поля", "📄 Договори"],
        ["💳 Виплати", "📊 Звіти"],
        ["📒 CRM", "🔎 Пошук"],
        ["🛡️ Адмінпанель"]
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
        ["🔍 Пошук договору"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню виплат ---
payments_menu_admin = ReplyKeyboardMarkup(
    [
        ["➕ Додати виплату"],
        ["📋 Перелік виплат"],
        ["🔍 Борг перед спадкоємцем"],
        ["💳 Звіти по виплатах"],
        ["◀️ Назад"],
    ],
    resize_keyboard=True,
)

payments_menu_user = ReplyKeyboardMarkup(
    [
        ["➕ Додати виплату"],
        ["📋 Перелік виплат"],
        ["🔍 Борг перед спадкоємцем"],
        ["◀️ Назад"],
    ],
    resize_keyboard=True,
)

# --- Меню звітів ---
reports_menu_admin = ReplyKeyboardMarkup(
    [
        ["📊 Зведення по орендній платі"],
        ["📈 Статистика по полях"],
        ["💸 Звіт по виплатах"],
        ["◀️ Назад"],
    ],
    resize_keyboard=True,
)

reports_menu_user = ReplyKeyboardMarkup(
    [
        ["📈 Статистика по полях"],
        ["◀️ Назад"],
    ],
    resize_keyboard=True,
)

# --- Меню пошуку ---
search_menu = ReplyKeyboardMarkup(
    [
        ["🔍 Пошук пайовика"],
        ["🔍 Пошук ділянки"],
        ["🔍 Пошук договору"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню CRM ---
crm_menu = ReplyKeyboardMarkup(
    [
        ["🧑‍🌾 Потенційні пайовики"],
        ["👤 Поточні пайовики"],
        ["📅 Планування і нагадування"],
        ["📨 Звернення та заяви"],
        ["◀️ Назад"]
    ],
    resize_keyboard=True
)

# --- Меню потенційних пайовиків ---
crm_potential_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати", "📋 Список"],
        ["🔍 Фільтр"],
        ["◀️ Назад"],
    ],
    resize_keyboard=True
)
crm_events_menu = ReplyKeyboardMarkup([
    ["➕ Додати подію"],
    ["📋 Переглянути події"],
    ["◀️ Назад"],
], resize_keyboard=True)

crm_inbox_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати звернення"],
        ["📂 Переглянути звернення"],
        ["◀️ Назад"],
    ],
    resize_keyboard=True,
)

# --- Адмінпанель ---
admin_panel_menu = ReplyKeyboardMarkup(
    [
        ["🏢 ТОВ-орендарі", "📄 Шаблони договорів"],
        ["👥 Користувачі"],
        ["↩️ Головне меню"]
    ],
    resize_keyboard=True
)
# ТОВ

admin_tov_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати ТОВ", "📋 Список ТОВ"],
        ["✏️ Редагувати ТОВ", "🗑️ Видалити ТОВ"],
        ["↩️ Адмінпанель"]
    ],
    resize_keyboard=True
)

# --- Меню шаблонів договорів ---
admin_templates_menu = ReplyKeyboardMarkup(
    [
        ["➕ Додати шаблон", "📋 Список шаблонів"],
        ["📘 Переглянути список змінних"],
        ["↩️ Адмінпанель"]
    ],
    resize_keyboard=True
)
