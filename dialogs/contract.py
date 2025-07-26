import os
from telegram import InlineKeyboardButton

import unicodedata
import re

def to_latin_filename(text, default="document.pdf"):
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = name.replace(" ", "_")
    name = re.sub(r'[^A-Za-z0-9_.-]', '', name)
    if not name or name.startswith(".pdf") or name.lower() == ".pdf":
        return default
    if not name.lower().endswith('.pdf'):
        name += ".pdf"
    return name
async def send_contract_pdf(update, context):
    query = update.callback_query
    _, _, contract_id, fname = query.data.split(":", 3)
    filename = to_latin_filename(fname)
    remote_path = f"contracts/{contract_id}/{filename}"
    tmp_path = f"temp_docs/{filename}"
    try:
        os.makedirs("temp_docs", exist_ok=True)
        download_file_ftp(remote_path, tmp_path)
        await query.message.reply_document(document=InputFile(tmp_path), filename=filename)
        os.remove(tmp_path)
    except Exception as e:
        await query.answer(f"Помилка при скачуванні файлу: {e}", show_alert=True)

# ...всередині функції картки contract_card:
btn_docs = InlineKeyboardButton("📷 Додати документи", callback_data=f"add_docs:contract:{contract.id}")

pdf_dir = f"files/contract/{contract.id}"
if os.path.exists(pdf_dir):
    for fname in os.listdir(pdf_dir):
        if fname.lower().endswith(".pdf"):
            keyboard.append([
                InlineKeyboardButton(f"📄 {fname}", callback_data=f"view_pdf:contract:{contract.id}:{fname}"),
                InlineKeyboardButton(f"🗑 Видалити {fname}", callback_data=f"delete_pdf:contract:{contract.id}:{fname}")
            ])
# Додаєш btn_docs та кнопки з keyboard у список інлайн-кнопок картки договору
