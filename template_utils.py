"""Utilities for validating contract templates."""

from __future__ import annotations

from typing import Any, Mapping, Iterable, Dict

import re
import zipfile
from collections import Counter

from docxtpl import DocxTemplate

from template_vars import TEMPLATE_VARIABLES, EMPTY_VALUE, SUPPORTED_VARS


# Mapping from variable placeholder to description
VAR_DESCRIPTIONS = {
    var: desc for cat in TEMPLATE_VARIABLES.values() for var, desc in cat["items"]
}
ALLOWED_VARS = set(VAR_DESCRIPTIONS.keys())


def find_unsupported_vars(template_path: str, template_type: str | None = None) -> list[str]:
    """Return list of placeholders not supported by the system."""
    doc = DocxTemplate(template_path)
    found = {f"{{{{{v}}}}}" for v in doc.get_undeclared_template_variables()}
    allowed = set(ALLOWED_VARS)
    if template_type == "multi":
        allowed.update(
            {
                "{{payers}}",
                "{{payer.full_name}}",
                "{{payer.tax_id}}",
                "{{payer.share}}",
                "{{loop.index}}",
            }
        )
    return sorted(found - allowed)


def extract_variables(path: str) -> Dict[str, int]:
    """Return mapping of variables found in DOCX to their occurrence count."""
    text_parts: list[str] = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                xml = z.read(name).decode("utf-8", errors="ignore")
                cleaned = re.sub(r"<[^>]+>", "", xml)
                text_parts.append(cleaned)

    full_text = "".join(text_parts)
    raw_vars = re.findall(r"\{\{.*?\}\}", full_text)

    counter: Counter[str] = Counter()
    for var in raw_vars:
        inner = re.sub(r"[^\w\.]", "", var[2:-2])
        if inner:
            counter[inner] += 1

    return dict(counter)


def analyze_template(
    template_path: str, context: Mapping[str, Any], template_type: str | None = None
) -> tuple[list[str], list[str], int, int, Dict[str, int]]:
    """Return missing and unsupported placeholders for a template.

    Parameters
    ----------
    template_path: str
        Path to the docx template.
    context: Mapping[str, Any]
        Values to substitute in the template.

    Returns
    -------
    tuple[list[str], list[str], int, int, Dict[str, int]]
        First item is a list of supported placeholders with empty values,
        second item is a list of unsupported placeholders.
        Third item is the total number of placeholders found in the template.
        Fourth item is the number of placeholders successfully filled.
        Fifth item is mapping of variable names to how many times they appear.
    """
    counts = extract_variables(template_path)
    missing: list[str] = []
    unsupported: list[str] = []
    filled = 0
    allowed_extra = set()
    if template_type == "multi":
        allowed_extra.update({"payers", "payer.full_name", "payer.tax_id", "payer.share", "loop.index"})
    for var, cnt in counts.items():
        if var not in SUPPORTED_VARS and var not in allowed_extra:
            unsupported.append(f"{{{{{var}}}}}")
            continue
        if var in allowed_extra:
            filled += cnt
            continue
        value = context.get(var)
        if value is None or (isinstance(value, str) and not str(value).strip()):
            missing.append(f"{{{{{var}}}}}")
        else:
            filled += cnt
    total = sum(counts.values())
    missing.sort()
    unsupported.sort()
    return missing, unsupported, total, filled, counts


def build_unresolved_message(
    missing: Iterable[str],
    unsupported: Iterable[str],
    total: int,
    *,
    filled: int | None = None,
    template_name: str | None = None,
) -> str:
    """Format message listing unresolved placeholders."""
    missing = list(missing)
    unsupported = list(unsupported)

    if not missing and not unsupported:
        if filled is not None:
            return f"✅ Усі {total} змінних знайдено та заповнено"
        return ""

    name_part = f" {template_name}" if template_name else ""
    header = f"⚠️ У шаблоні{name_part} знайдено {total} змінних"
    lines = [header]
    if filled is not None:
        lines.append(f"✅ Заповнено: {filled}")
    lines.append("❌ Не заповнено:")

    for var in sorted(missing + unsupported):
        if var in unsupported:
            lines.append(f"{var} — змінна не підтримується")
        else:
            desc = VAR_DESCRIPTIONS.get(var, "")
            if desc:
                lines.append(f"{var} — {desc} не вказано")
            else:
                lines.append(f"{var} — значення відсутнє")
    lines.append(f"📝 У шаблон буде підставлено: {EMPTY_VALUE}")
    return "\n".join(lines)

