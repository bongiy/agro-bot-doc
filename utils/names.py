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
