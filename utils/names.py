def short_name(full_name: str) -> str:
    """Return abbreviated version of Ukrainian full name.

    Expected input: "Surname Name Patronymic" or "Surname Name".
    Output example: "Іван І." for "Іванов Іван".
    If the name doesn't contain at least two parts, return it unchanged.
    """
    parts = full_name.split()
    if len(parts) >= 2:
        first_name = parts[1]
        surname_initial = parts[0][0].upper() + "."
        return f"{first_name} {surname_initial}"
    return full_name


def format_payers_line(payers: list[str]) -> str:
    """Return formatted line with payer names for contract lists.

    Uses :func:`short_name` to abbreviate each payer and applies the
    "Pайовик"/"Пайовики" prefix depending on the number of participants.
    The result matches the formatting used in contract cards.
    """
    import html

    names = [short_name(p) for p in payers if p]
    if not names:
        return "👤 Пайовик: —"
    if len(names) == 1:
        return f"👤 Пайовик: {html.escape(names[0])}"
    shown = ", ".join(html.escape(n) for n in names[:2])
    if len(names) > 2:
        shown += f" +{len(names) - 2} ще..."
    return f"🧑‍🤝‍🧑 Пайовики: {shown}"
