btn_docs = InlineKeyboardButton("📷 Додати документи", callback_data=f"add_docs:contract:{contract.id}")
pdf_dir = f"files/contract/{contract.id}"
if os.path.exists(pdf_dir):
    for fname in os.listdir(pdf_dir):
        if fname.lower().endswith(".pdf"):
            keyboard.append([InlineKeyboardButton(f"📄 {fname}", callback_data=f"view_pdf:contract:{contract.id}:{fname}")])
            keyboard.append([InlineKeyboardButton(f"🗑 Видалити {fname}", callback_data=f"delete_pdf:contract:{contract.id}:{fname}")])
