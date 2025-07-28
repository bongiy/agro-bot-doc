from __future__ import annotations

import os
import shutil
from typing import Any, Mapping, Iterable

from docx import Document

from template_vars import SUPPORTED_VARS, EMPTY_VALUE
from template_utils import extract_variables
from ftp_utils import download_file_ftp, upload_file_ftp
from contract_pdf import docx_to_pdf


def load_template(remote_path: str, local_dir: str = "temp_docs") -> str:
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, os.path.basename(remote_path))
    download_file_ftp(remote_path, local_path)
    return local_path


def read_template_vars(template_path: str) -> set[str]:
    return set(extract_variables(template_path).keys())


def build_context(template_vars: Iterable[str], values: Mapping[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for var in template_vars:
        if var in SUPPORTED_VARS:
            value = values.get(var)
            context[var] = value if value not in (None, "") else EMPTY_VALUE
        else:
            context[var] = EMPTY_VALUE
    return context


def generate_log(template_name: str, total: int, filled: list[str], missing: list[str], unsupported: list[str]) -> str:
    lines = [f"⚠️ У шаблоні {template_name} знайдено {total} змінних"]
    lines.append(f"✅ Заповнено: {len(filled)}")
    if missing or unsupported:
        lines.append("❌ Не заповнено:")
        for var in missing:
            lines.append(var)
        for var in unsupported:
            lines.append(f"{var} — змінна не підтримується")
        lines.append(f"📝 У шаблон буде підставлено: {EMPTY_VALUE}")
    return "\n".join(lines)


def fill_doc(template_path: str, context: Mapping[str, Any], output_docx: str) -> None:
    doc = Document(template_path)
    placeholders = {f"{{{{{k}}}}}": str(v) for k, v in context.items()}

    def replace_in_paragraph(paragraph):
        for ph, val in placeholders.items():
            if ph in paragraph.text:
                paragraph.text = paragraph.text.replace(ph, val)

    def replace_in_table(table):
        for row in table.rows:
            for cell in row.cells:
                for ph, val in placeholders.items():
                    if ph in cell.text:
                        cell.text = cell.text.replace(ph, val)

    for p in doc.paragraphs:
        replace_in_paragraph(p)
    for t in doc.tables:
        replace_in_table(t)
    for section in doc.sections:
        hdr = section.header
        for p in hdr.paragraphs:
            replace_in_paragraph(p)
        for t in hdr.tables:
            replace_in_table(t)
        ftr = section.footer
        for p in ftr.paragraphs:
            replace_in_paragraph(p)
        for t in ftr.tables:
            replace_in_table(t)

    doc.save(output_docx)


def generate_contract(
    template_remote_path: str,
    values: Mapping[str, Any],
    payer_name: str,
    contract_number: str,
    year: int,
    *,
    dev: bool = False,
) -> tuple[str, str]:
    template_local = load_template(template_remote_path)
    template_vars = read_template_vars(template_local)
    context = build_context(template_vars, values)

    filled = [v for v in template_vars if context[v] != EMPTY_VALUE]
    missing = [f"{{{{{v}}}}}" for v in template_vars if context[v] == EMPTY_VALUE and v in SUPPORTED_VARS and values.get(v) in (None, "")]
    unsupported = [f"{{{{{v}}}}}" for v in template_vars if v not in SUPPORTED_VARS]

    log = generate_log(os.path.basename(template_remote_path), len(template_vars), filled, missing, unsupported)

    os.makedirs("temp_docs", exist_ok=True)
    filled_docx = os.path.join("temp_docs", "filled_contract.docx")
    fill_doc(template_local, context, filled_docx)
    pdf_local = os.path.join("temp_docs", "contract.pdf")
    docx_to_pdf(filled_docx, pdf_local)
    os.remove(filled_docx)

    filename = f"\u0414\u043e\u0433\u043e\u0432\u0456\u0440_{contract_number}_{payer_name}.pdf"
    remote_dir = f"contracts/{year}/{payer_name}"
    remote_path = f"{remote_dir}/{filename}"

    if dev:
        os.makedirs(remote_dir, exist_ok=True)
        shutil.move(pdf_local, remote_path)
    else:
        upload_file_ftp(pdf_local, remote_path)
        os.remove(pdf_local)

    os.remove(template_local)

    return remote_path, log

