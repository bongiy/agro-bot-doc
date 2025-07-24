import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from PIL import Image
from fpdf import FPDF
from db import database, Payer, LandPlot  # Contract додай, коли буде

SELECT_DOC_TYPE, COLLECT_PHOTO = range(2)

DOC_TYPES = {
    "land": [
        "Державний акт", "Витяг про реєстрацію", "Свідоцтво про спадщину",
        "Технічна документація", "Інші документи"
    ],
    "payer_passport": ["Паспорт", "ІПН", "Інші документи"],
    "payer_id": ["ID картка", "ІПН", "Витяг про місце проживання", "Інші документи"],
    "contract": ["Скан договору", "Витяг про реєстрацію права оренди", "Додаткові угоди", "Заяви та звернення"],
}

async def start_add_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, entity_type, entity_id = query.data.split(":")
    context.user_data["entity_type"] = entity_type
    context.user_data["entity_id"] = entity_id

    # --- Формуємо “людську” папку ---
    if entity_type.startswith("payer"):
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == int(entity_id)))
        if not payer:
            await query.message.reply_text("Пайовик не знайдений.")
            return ConversationHandler.END
        folder = f"files/payer/{payer.name.replace(' ', '_')}_{payer.id}"
    elif entity_type == "land":
        land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == int(entity_id)))
        if not land:
            await query.message.reply_text("Ділянка не знайдена.")
            return ConversationHandler.END
        cadaster = land.cadaster.replace(':', '_')
        folder = f"files/land/{cadaster}"
    elif entity_type == "contract":
        # (Додати для договору аналогічну логіку коли реалізуєш contracts)
        folder = f"files/contract/{entity_id}"
    else:
        folder = f"files/{entity_type}/{entity_id}"
    context.user_data["pdf_folder"] = folder

    doc_types = DOC_TYPES.get(entity_type, DOC_TYPES["land"])
    keyboard = [[InlineKeyboardButton(dt, callback_data=f"doc_type:{dt}")] for dt in doc_types]
    await query.message.edit_text(
        "Оберіть тип документу для завантаження фото:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data["photos"] = []
    return SELECT_DOC_TYPE

async def select_doc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    doc_type = query.data.split(":", 1)[1]
    context.user_data["current_doc_type"] = doc_type
    context.user_data["photos"] = []
    await query.message.edit_text(
        f"Надішліть одне чи кілька фото для документу «{doc_type}».\n"
        "Коли завантажите все — натисніть кнопку «Готово».",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Готово", callback_data="photos_done")]
        ])
    )
    return COLLECT_PHOTO

async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file_id = photo.file_id
    context.user_data.setdefault("photos", []).append(file_id)
    await update.message.reply_text("Фото отримано. Ще надсилайте або натисніть «Готово».")

async def finish_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    folder = context.user_data["pdf_folder"]
    doc_type = context.user_data["current_doc_type"]
    photos = context.user_data.get("photos", [])
    if not photos:
        await query.message.reply_text("Ви не надіслали жодного фото. Скасовано.")
        return ConversationHandler.END

    # Завантажуємо фото, формуємо PDF
    image_files = []
    os.makedirs(folder, exist_ok=True)
    for i, file_id in enumerate(photos, 1):
        photo_file = await context.bot.get_file(file_id)
        file_path = f"{folder}/photo_{i}.jpg"
        await photo_file.download_to_drive(file_path)
        image_files.append(file_path)
    # Створення PDF
    pdf_path = f"{folder}/{doc_type}.pdf"
    pdf = FPDF()
    for image in image_files:
        img = Image.open(image)
        pdf.add_page()
        img_w, img_h = img.size
        pdf_w, pdf_h = pdf.w, pdf.h
        ratio = min(pdf_w / img_w, pdf_h / img_h)
        w, h = img_w * ratio, img_h * ratio
        img.save(image)  # перезапис у формат JPG, якщо потрібно
        pdf.image(image, x=0, y=0, w=w, h=h)
        img.close()
        os.remove(image)
    pdf.output(pdf_path)
    await query.message.reply_text(f"Документ «{doc_type}» додано як PDF у {os.path.basename(folder)}.")
    return ConversationHandler.END

add_docs_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_docs, pattern=r"^add_docs:\w+:\d+$")],
    states={
        SELECT_DOC_TYPE: [CallbackQueryHandler(select_doc_type, pattern=r"^doc_type:.+")],
        COLLECT_PHOTO: [
            MessageHandler(filters.PHOTO, collect_photo),
            CallbackQueryHandler(finish_photos, pattern="^photos_done$"),
        ],
    },
    fallbacks=[]
)

# --- Для перегляду PDF:
async def send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    query = update.callback_query
    _, entity_type, entity_id, fname = query.data.split(":", 3)
    # Та сама логіка для “людської” папки:
    if entity_type.startswith("payer"):
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == int(entity_id)))
        folder = f"files/payer/{payer.name.replace(' ', '_')}_{payer.id}"
    elif entity_type == "land":
        land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == int(entity_id)))
        cadaster = land.cadaster.replace(':', '_')
        folder = f"files/land/{cadaster}"
    elif entity_type == "contract":
        folder = f"files/contract/{entity_id}"
    else:
        folder = f"files/{entity_type}/{entity_id}"

    pdf_path = f"{folder}/{fname}"
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            await query.message.reply_document(f, filename=fname)
    else:
        await query.answer("PDF файл не знайдено!", show_alert=True)

# --- Видалення PDF:
async def delete_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    query = update.callback_query
    _, entity_type, entity_id, fname = query.data.split(":", 3)
    if entity_type.startswith("payer"):
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == int(entity_id)))
        folder = f"files/payer/{payer.name.replace(' ', '_')}_{payer.id}"
    elif entity_type == "land":
        land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == int(entity_id)))
        cadaster = land.cadaster.replace(':', '_')
        folder = f"files/land/{cadaster}"
    elif entity_type == "contract":
        folder = f"files/contract/{entity_id}"
    else:
        folder = f"files/{entity_type}/{entity_id}"

    pdf_path = f"{folder}/{fname}"
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        await query.answer("PDF видалено!", show_alert=True)
        await query.message.edit_text("Документ видалено. Оновіть картку для перегляду змін.")
    else:
        await query.answer("PDF не знайдено!", show_alert=True)
