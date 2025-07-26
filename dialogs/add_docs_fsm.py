import os
import re
import unicodedata
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from PIL import Image
from fpdf import FPDF
from db import database, Payer, LandPlot, UploadedDocs
from ftp_utils import upload_file_ftp, download_file_ftp, delete_file_ftp
import sqlalchemy

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


def to_latin_filename(text, default="document.pdf"):
    import unicodedata, re
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^A-Za-z0-9]+', '_', name)  # усе крім латиниці та цифр на _
    name = name.strip('_')
    if not name or name.lower() == ".pdf" or name.endswith("_.pdf"):
        return default
    if not name.lower().endswith('.pdf'):
        name += ".pdf"
    return name

def to_latin_folder(text, default="doc_folder"):
    import unicodedata, re
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^A-Za-z0-9]+', '_', name)
    name = name.strip('_')
    if not name:
        return default
    return name

    # --- "людська" назва для папки/шляху, одразу латиницею ---
    if entity_type.startswith("payer"):
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == int(entity_id)))
        if not payer:
            await query.message.reply_text("Пайовик не знайдений.")
            return ConversationHandler.END
        folder_name = to_latin_folder(f"{payer.name.replace(' ', '_')}_{payer.id}")
    elif entity_type == "land":
        land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == int(entity_id)))
        if not land:
            await query.message.reply_text("Ділянка не знайдена.")
            return ConversationHandler.END
        folder_name = to_latin_folder(land.cadaster.replace(':', '_'))
    elif entity_type == "contract":
        folder_name = to_latin_folder(f"{entity_id}")
    else:
        folder_name = to_latin_folder(f"{entity_type}_{entity_id}")

    context.user_data["ftp_folder"] = folder_name

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
    folder_name = context.user_data["ftp_folder"]
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
    pdf_filename = to_latin_filename(f"{folder_name}_{doc_type}")
    pdf_path = f"temp_docs/{pdf_filename}"
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

    # === Завантаження на FTP (шлях лише латиницею!) ===
    remote_dir = f"{entity_type}s/{folder_name}"
    doc_type_file = to_latin_filename(doc_type)
    remote_file = f"{remote_dir}/{doc_type_file}"
    upload_file_ftp(pdf_path, remote_file)
    os.remove(pdf_path)

    # Оновлюємо БД
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
            remote_path=remote_file
        )
    )

    await query.message.reply_text(
        f"Документ «{doc_type}» додано та збережено у системі."
    )
    return ConversationHandler.END

# ==== ВІДПРАВКА PDF з FTP ====
async def send_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])

    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        remote_path = row['remote_path']
        filename = to_latin_filename(os.path.basename(remote_path))
        tmp_path = f"temp_docs/{filename}"
        try:
            os.makedirs("temp_docs", exist_ok=True)
            download_file_ftp(remote_path, tmp_path)
            print("Send:", tmp_path, filename)
            await query.message.reply_document(document=InputFile(tmp_path), filename=filename)
            os.remove(tmp_path)
        except Exception as e:
            await query.answer(f"Помилка при скачуванні файлу: {e}", show_alert=True)
    else:
        await query.answer("Документ не знайдено!", show_alert=True)

# ==== ВИДАЛЕННЯ PDF з FTP ====
async def delete_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        try:
            delete_file_ftp(row['remote_path'])
        except Exception:
            pass
        await database.execute(UploadedDocs.delete().where(UploadedDocs.c.id == doc_id))
        await query.answer("Документ видалено!")
        await query.message.edit_text("Документ видалено. Оновіть картку для перегляду змін.")
    else:
        await query.answer("Документ не знайдено!", show_alert=True)

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
