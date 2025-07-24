import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from PIL import Image
from fpdf import FPDF
from db import database, Payer, LandPlot, UploadedDocs  # додано UploadedDocs
from drive_utils import upload_pdf_to_drive

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

    # --- "людська" назва для Google Drive ---
    if entity_type.startswith("payer"):
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == int(entity_id)))
        if not payer:
            await query.message.reply_text("Пайовик не знайдений.")
            return ConversationHandler.END
        folder_name = f"{payer.name.replace(' ', '_')}_{payer.id}"
    elif entity_type == "land":
        land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == int(entity_id)))
        if not land:
            await query.message.reply_text("Ділянка не знайдена.")
            return ConversationHandler.END
        folder_name = land.cadaster.replace(':', '_')
    elif entity_type == "contract":
        folder_name = f"{entity_id}"
    else:
        folder_name = f"{entity_type}_{entity_id}"

    context.user_data["gdrive_folder"] = folder_name

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
    folder_name = context.user_data["gdrive_folder"]
    doc_type = context.user_data["current_doc_type"]
    photos = context.user_data.get("photos", [])
    entity_type = context.user_data["entity_type"]
    entity_id = int(context.user_data["entity_id"])

    if not photos:
        await query.message.reply_text("Ви не надіслали жодного фото. Скасовано.")
        return ConversationHandler.END

    # Тимчасово зберігаємо фото
    image_files = []
    os.makedirs("temp_docs", exist_ok=True)
    for i, file_id in enumerate(photos, 1):
        photo_file = await context.bot.get_file(file_id)
        file_path = f"temp_docs/photo_{i}.jpg"
        await photo_file.download_to_drive(file_path)
        image_files.append(file_path)

    # Створюємо PDF
    pdf_path = f"temp_docs/{folder_name}_{doc_type}.pdf"
    pdf = FPDF()
    for image in image_files:
        img = Image.open(image)
        pdf.add_page()
        img_w, img_h = img.size
        pdf_w, pdf_h = pdf.w, pdf.h
        ratio = min(pdf_w / img_w, pdf_h / img_h)
        w, h = img_w * ratio, img_h * ratio
        img.save(image)
        pdf.image(image, x=0, y=0, w=w, h=h)
        img.close()
        os.remove(image)
    pdf.output(pdf_path)

    # --- Google Drive Upload ---
    file_name = f"{doc_type}.pdf"
    file_id, web_link = upload_pdf_to_drive(pdf_path, file_name)
    await query.message.reply_text(
        f"Документ «{doc_type}» додано на Google Drive.\n"
        f"[Відкрити PDF]({web_link})",
        parse_mode="Markdown"
    )
    os.remove(pdf_path)

    # --- Зберігаємо file_id та web_link у БД ---
    import sqlalchemy
    # Видаляємо старий запис (doc_type для entity_type/entity_id унікальний)
    await database.execute(
        UploadedDocs.delete().where(
            (UploadedDocs.c.entity_type == entity_type) &
            (UploadedDocs.c.entity_id == entity_id) &
            (UploadedDocs.c.doc_type == doc_type)
        )
    )
    await database.execute(
        UploadedDocs.insert().values(
            entity_type=entity_type,
            entity_id=entity_id,
            doc_type=doc_type,
            gdrive_file_id=file_id,
            web_link=web_link
        )
    )
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
