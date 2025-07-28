"""Utilities for validating contract templates."""

from __future__ import annotations

from typing import Any, Mapping, Iterable

from docxtpl import DocxTemplate

from template_vars import TEMPLATE_VARIABLES, EMPTY_VALUE, SUPPORTED_VARS


# Mapping from variable placeholder to description
VAR_DESCRIPTIONS = {
    var: desc for cat in TEMPLATE_VARIABLES.values() for var, desc in cat["items"]
}
ALLOWED_VARS = set(VAR_DESCRIPTIONS.keys())


def find_unsupported_vars(template_path: str) -> list[str]:
    """Return list of placeholders not supported by the system."""
    doc = DocxTemplate(template_path)
    found = {f"{{{{{v}}}}}" for v in doc.get_undeclared_template_variables()}
    return sorted(found - ALLOWED_VARS)


def analyze_template(
    template_path: str, context: Mapping[str, Any]
) -> tuple[list[str], list[str], int]:
    """Return missing and unsupported placeholders for a template.

    Parameters
    ----------
    template_path: str
        Path to the docx template.
    context: Mapping[str, Any]
        Values to substitute in the template.

    Returns
    -------
    tuple[list[str], list[str], int]
        First item is a list of supported placeholders with empty values,
        second item is a list of unsupported placeholders.
        Third item is the total number of placeholders found in the template.
    """
    doc = DocxTemplate(template_path)
    vars_found = list(doc.get_undeclared_template_variables())
    all_vars = {f"{{{{{v}}}}}" for v in vars_found}
    missing_in_ctx = {
        f"{{{{{v}}}}}" for v in doc.get_undeclared_template_variables(context=context)
    }
    missing_values = {
        f"{{{{{k}}}}}"
        for k, v in context.items()
        if (v is None or (isinstance(v, str) and not str(v).strip()))
        and f"{{{{{k}}}}}" in all_vars
    }
    unsupported = sorted(all_vars - ALLOWED_VARS)
    supported_missing = sorted((missing_in_ctx | missing_values) & ALLOWED_VARS)
    total = len(all_vars)
    return supported_missing, unsupported, total


def build_unresolved_message(
    missing: Iterable[str], unsupported: Iterable[str], total: int
) -> str:
    """Format message listing unresolved placeholders."""
    missing = list(missing)
    unsupported = list(unsupported)
    if not missing and not unsupported:
        return f"✅ Усі {total} змінних знайдено та заповнено"

    lines = ["⚠️ У шаблоні знайдено незаповнені змінні:", ""]
    for var in sorted(missing + unsupported):
        if var in unsupported:
            lines.append(f"{var} — змінна не підтримується")
        else:
            desc = VAR_DESCRIPTIONS.get(var, "")
            if desc:
                lines.append(f"{var} — значення відсутнє ({desc} не вказано)")
            else:
                lines.append(f"{var} — значення відсутнє")
    lines.append(f"📎 У шаблон буде підставлено: {EMPTY_VALUE}")
    return "\n".join(lines)

