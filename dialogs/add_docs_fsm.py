import os
import re
import time
import unicodedata
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ReplyKeyboardMarkup
from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from PIL import Image
from fpdf import FPDF
from db import database, Payer, LandPlot, UploadedDocs
from ftp_utils import upload_file_ftp, delete_file_ftp, download_file_ftp_to_memory
import sqlalchemy
from PyPDF2 import PdfReader, PdfWriter

SELECT_DOC_TYPE, COLLECT_PHOTO, ASK_MORE = range(3)

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
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^A-Za-z0-9]+', '_', name)
    name = name.strip('_')
    if not name or name.lower() == ".pdf" or name.endswith("_.pdf"):
        return default
    if not name.lower().endswith('.pdf'):
        name += ".pdf"
    return name

def to_latin_folder(text, default="doc_folder"):
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^A-Za-z0-9]+', '_', name)
    name = name.strip('_')
    if not name:
        return default
    return name

def to_latin(text, default="file"):
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^A-Za-z0-9]+', '_', name)
    name = name.strip('_')
    return name or default

def repack_pdf(input_path, output_path):
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({
        '/Title': 'Документ',
        '/Producer': 'AgroBot',
    })
    with open(output_path, "wb") as f:
        writer.write(f)

async def start_add_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, entity_type, entity_id = query.data.split(":")
    context.user_data["entity_type"] = entity_type
    context.user_data["entity_id"] = entity_id

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
    context.user_data["doc_types"] = doc_types
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
    doc_type = context.user_data["current_doc_type"]
    photos = context.user_data.get("photos", [])
    entity_type = context.user_data["entity_type"]
    entity_id = int(context.user_data["entity_id"])

    if not photos:
        await query.message.reply_text("Ви не надіслали жодного фото. Скасовано.")
        return ConversationHandler.END

    # === Формування папки (КИРИЛИЦЯ) та імені файлу (ЛАТИНИЦЯ) ===
    if entity_type.startswith("payer"):
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == entity_id))
        pib = payer.name if payer else f"payer_{entity_id}"  # кирилиця
        ipn = str(payer.ipn) if payer and payer.ipn else str(entity_id)
        folder_name = pib
        doc_type_file = to_latin(f"{ipn}_{doc_type}")
        if not doc_type_file.lower().endswith('.pdf'):
            doc_type_file += ".pdf"
        remote_dir = f"payer_ids/{folder_name}"
        remote_file = f"{remote_dir}/{doc_type_file}"
    elif entity_type == "land":
        land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == entity_id))
        cad = land.cadaster.replace(':', '_') if land else str(entity_id)
        if land and getattr(land, "payer_id", None):
            payer = await database.fetch_one(Payer.select().where(Payer.c.id == land.payer_id))
            pib = payer.name if payer else "landowner"
        else:
            pib = "landowner"
        folder_name = pib
        doc_type_file = to_latin(f"{cad}_{doc_type}")
        if not doc_type_file.lower().endswith('.pdf'):
            doc_type_file += ".pdf"
        remote_dir = f"lands/{folder_name}"
        remote_file = f"{remote_dir}/{doc_type_file}"
    elif entity_type == "field":
        field_id = str(entity_id)
        field = await database.fetch_one(Field.select().where(Field.c.id == entity_id))
        field_name = field.name if field and hasattr(field, "name") and field.name else f"field_{field_id}"
        folder_name = field_name
        doc_type_file = to_latin(f"{field_id}_{doc_type}_{int(time.time())}")
        if not doc_type_file.lower().endswith('.pdf'):
            doc_type_file += ".pdf"
        remote_dir = f"fields/{folder_name}"
        remote_file = f"{remote_dir}/{doc_type_file}"
    elif entity_type == "contract":
        payer = await database.fetch_one(Payer.select().where(Payer.c.id == payer_id))
        pib = payer.name if payer else f"payer_{entity_id}"
        ipn = str(payer.ipn) if payer and payer.ipn else str(entity_id)
        folder_name = pib
        doc_type_file = to_latin(f"{ipn}_{entity_id}_{doc_type}")
        if not doc_type_file.lower().endswith('.pdf'):
            doc_type_file += ".pdf"
        remote_dir = f"contracts/{folder_name}"
        remote_file = f"{remote_dir}/{doc_type_file}"
    else:
        folder_name = f"{entity_type}_{entity_id}"
        doc_type_file = to_latin(f"{entity_type}_{entity_id}_{doc_type}")
        if not doc_type_file.lower().endswith('.pdf'):
            doc_type_file += ".pdf"
        remote_dir = f"{entity_type}s/{folder_name}"
        remote_file = f"{remote_dir}/{doc_type_file}"

    # === Зберігаємо фото та формуємо PDF ===
    image_files = []
    os.makedirs("temp_docs", exist_ok=True)
    for i, file_id in enumerate(photos, 1):
        photo_file = await context.bot.get_file(file_id)
        file_path = f"temp_docs/photo_{i}.jpg"
        await photo_file.download_to_drive(file_path)
        image_files.append(file_path)

    pdf_path = f"temp_docs/{doc_type_file}"
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
    repack_pdf(pdf_path, pdf_path)
    upload_file_ftp(pdf_path, remote_file)
    os.remove(pdf_path)

    # === Оновлюємо БД ===
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
        f"Документ «{doc_type}» додано та збережено у системі.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Додати ще", callback_data="more_docs")],
            [InlineKeyboardButton("Завершити", callback_data="finish_docs")],
        ])
    )
    return ASK_MORE

async def more_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doc_types = context.user_data.get("doc_types", DOC_TYPES.get(context.user_data.get("entity_type"), DOC_TYPES["land"]))
    keyboard = [[InlineKeyboardButton(dt, callback_data=f"doc_type:{dt}")] for dt in doc_types]
    await query.message.edit_text(
        "Оберіть тип документу для завантаження фото:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_DOC_TYPE

async def finish_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = context.user_data.pop("post_create_msg", "Документи додано.")
    markup = context.user_data.pop("post_create_markup", None)

    if isinstance(markup, ReplyKeyboardMarkup):
        await query.message.delete()
        await query.message.reply_text(text, reply_markup=markup)
    elif markup:
        await query.message.edit_text(text, reply_markup=markup)
    else:
        await query.message.edit_text(text)

    context.user_data.clear()
    return ConversationHandler.END

# ==== ВІДПРАВКА PDF з FTP у RAM ====
async def send_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        remote_path = row['remote_path']
        bio, filename = download_file_ftp_to_memory(remote_path)
        await query.message.reply_document(document=InputFile(bio, filename=filename))
        await query.answer("Документ відправлено у PDF!", show_alert=False)
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
            CallbackQueryHandler(finish_photos, pattern="^photos_done$")
        ],
        ASK_MORE: [
            CallbackQueryHandler(more_docs, pattern="^more_docs$"),
            CallbackQueryHandler(finish_docs, pattern="^finish_docs$")
        ],
    },
    fallbacks=[]
)
