"""Utilities for validating contract templates."""

from __future__ import annotations

from typing import Any, Mapping, Iterable

from docxtpl import DocxTemplate

from template_vars import TEMPLATE_VARIABLES, EMPTY_VALUE


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


def analyze_template(template_path: str, context: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return missing and unsupported placeholders for a template.

    Parameters
    ----------
    template_path: str
        Path to the docx template.
    context: Mapping[str, Any]
        Values to substitute in the template.

    Returns
    -------
    tuple[list[str], list[str]]
        First item is a list of supported placeholders with empty values,
        second item is a list of unsupported placeholders.
    """
    doc = DocxTemplate(template_path)
    all_vars = {f"{{{{{v}}}}}" for v in doc.get_undeclared_template_variables()}
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
    return supported_missing, unsupported


def build_unresolved_message(missing: Iterable[str], unsupported: Iterable[str]) -> str | None:
    """Format message listing unresolved placeholders."""
    missing = list(missing)
    unsupported = list(unsupported)
    count = len(missing) + len(unsupported)
    if count == 0:
        return None
    lines = [f"⚠️ Не вдалося заповнити {count} змінних:", ""]
    for var in sorted(missing + unsupported):
        if var in unsupported:
            lines.append(f"{var} — така змінна не підтримується")
        else:
            desc = VAR_DESCRIPTIONS.get(var, "")
            lines.append(f"{var} — {desc} не заповнено")
    lines.append(f"Буде підставлено: {EMPTY_VALUE} у шаблон")
    return "\n".join(lines)

