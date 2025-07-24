import os
from telegram import InlineKeyboardButton

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
