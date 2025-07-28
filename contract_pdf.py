from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from docxtpl import DocxTemplate
from docx2pdf import convert

from template_vars import with_default, date_to_words


def format_area(area: float | int | str | None) -> str:
    if area is None or area == "":
        return with_default(None)
    try:
        return f"{float(area):.4f}"
    except Exception:
        return str(area)


def format_money(amount: float | Decimal | str | None) -> str:
    if amount is None or amount == "":
        return with_default(None)
    try:
        value = float(amount)
    except Exception:
        try:
            value = float(str(amount).replace(",", "."))
        except Exception:
            return str(amount)
    parts = f"{value:,.2f}".split(".")
    parts[0] = parts[0].replace(",", " ")
    return f"{parts[0]},{parts[1]} грн"


def format_share(share: float | str | None) -> str:
    if share is None or share == "":
        return with_default(None)
    return str(share)


def format_date(value: str | datetime | None) -> str:
    """Format date in '27 липня 2025' style."""
    if value in (None, ""):
        return with_default(None)
    if isinstance(value, datetime):
        return date_to_words(value.strftime("%d.%m.%Y"))
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(str(value), fmt)
            return date_to_words(dt.strftime("%d.%m.%Y"))
        except Exception:
            continue
    return str(value)


def docx_to_pdf(docx_path: str, pdf_path: str) -> None:
    try:
        convert(docx_path, pdf_path)
    except Exception:
        libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice:
            raise
        subprocess.run([
            libreoffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            os.path.dirname(pdf_path),
            docx_path,
        ], check=True)
        generated = os.path.join(
            os.path.dirname(pdf_path),
            os.path.splitext(os.path.basename(docx_path))[0] + ".pdf",
        )
        os.replace(generated, pdf_path)


def render_template(template_path: str, context: Mapping[str, Any], output_dir: str) -> str:
    doc = DocxTemplate(template_path)
    doc.render(context)
    os.makedirs(output_dir, exist_ok=True)
    docx_path = os.path.join(output_dir, "contract.docx")
    doc.save(docx_path)
    pdf_path = os.path.join(output_dir, "contract.pdf")
    docx_to_pdf(docx_path, pdf_path)
    os.remove(docx_path)
    return pdf_path


def generate_contract(
    template_path: str,
    variables: Mapping[str, Any],
    payer_name: str,
    contract_number: str,
    year: int,
    *,
    dev: bool = False,
) -> str:
    pdf_local = render_template(template_path, variables, "temp_docs")
    filename = f"\u0414\u043e\u0433\u043e\u0432\u0456\u0440_{contract_number}_{payer_name}.pdf"
    remote_dir = f"contracts/{year}/{payer_name}"
    remote_path = f"{remote_dir}/{filename}"
    if dev:
        os.makedirs(remote_dir, exist_ok=True)
        shutil.move(pdf_local, remote_path)
    else:
        from ftp_utils import upload_file_ftp

        upload_file_ftp(pdf_local, remote_path)
        os.remove(pdf_local)
    return remote_path
