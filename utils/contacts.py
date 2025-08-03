import re

__all__ = ["normalize_phone", "normalize_edrpou"]


def normalize_phone(phone: str) -> str:
    """Normalize phone to +380XXXXXXXXX format.

    Non-digit characters are stripped. If the number starts with 0 or
    missing country code, it will be converted to the Ukrainian +380
    prefix. Returns the cleaned phone string with leading '+' sign.
    """
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("380") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:
        return "+38" + digits
    if len(digits) == 9:
        return "+380" + digits
    if digits and not digits.startswith("+"):
        return "+" + digits
    return phone.strip()


def normalize_edrpou(edrpou: str) -> str:
    """Return EDRPOU as an 8-digit string."""
    digits = re.sub(r"\D", "", edrpou or "")
    return digits[:8].zfill(8)
