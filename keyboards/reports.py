from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def status_filter_kb() -> InlineKeyboardMarkup:
    """Keyboard for selecting payment status filter."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Очікує", callback_data="status:pending"),
                InlineKeyboardButton("Виплачено", callback_data="status:paid"),
            ],
            [
                InlineKeyboardButton("Частково", callback_data="status:partial"),
                InlineKeyboardButton("Виплата спадкоємцю", callback_data="status:heir"),
            ],
            [InlineKeyboardButton("Пропустити", callback_data="status:any")],
        ]
    )


def rent_status_filter_kb() -> InlineKeyboardMarkup:
    """Keyboard for selecting rent payment summary status filter."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Очікує", callback_data="rent_status:pending"),
                InlineKeyboardButton("Частково", callback_data="rent_status:partial"),
            ],
            [InlineKeyboardButton("Оплачено", callback_data="rent_status:paid")],
            [InlineKeyboardButton("Пропустити", callback_data="rent_status:any")],
        ]
    )


def heirs_filter_kb() -> InlineKeyboardMarkup:
    """Keyboard to choose whether to show only heir payments."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Лише спадкоємці", callback_data="heirs:yes"),
                InlineKeyboardButton("Всі", callback_data="heirs:no"),
            ]
        ]
    )


def report_nav_kb(has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    """Pagination and export keyboard."""
    rows: list[list[InlineKeyboardButton]] = []
    nav_row: list[InlineKeyboardButton] = []
    if has_prev:
        nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data="payrep_prev"))
    if has_next:
        nav_row.append(InlineKeyboardButton("Вперед ▶️", callback_data="payrep_next"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("📤 Експорт", callback_data="payrep_export")])
    return InlineKeyboardMarkup(rows)
