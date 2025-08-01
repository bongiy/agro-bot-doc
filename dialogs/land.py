import os
import unicodedata
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile,
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
)
from keyboards.menu import lands_menu
from db import database, LandPlot, Field, Payer, UploadedDocs, LandPlotOwner
from dialogs.post_creation import prompt_add_docs
import sqlalchemy
from ftp_utils import download_file_ftp, delete_file_ftp

# --- Стани для FSM додавання ділянки ---
(
    ASK_CADASTER,
    ASK_AREA,
    ASK_NGO,
    ASK_FIELD,
    CHOOSE_COUNCIL,
    INPUT_REGION,
    INPUT_DISTRICT,
    INPUT_COUNCIL,
    ASK_OWNER_COUNT,
    ASK_OWNER,
    SEARCH_OWNER,
    CHOOSE_OWNER,
) = range(12)

COUNCIL_OPTIONS = [
    "Городоцька сільська рада",
    "Шпанівська сільська рада",
    "Дядьковецька сільська рада",
    "Сатиївська сільська рада",
    "Великоомелянська сільська рада",
]

def to_latin_filename(text, default="document.pdf"):
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = name.replace(" ", "_")
    name = re.sub(r'[^A-Za-z0-9_.-]', '', name)
    if not name or name.startswith(".pdf") or name.lower() == ".pdf":
        return default
    if not name.lower().endswith('.pdf'):
        name += ".pdf"
    return name

# ==== ДОДАВАННЯ ДІЛЯНКИ ====
async def add_land_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть кадастровий номер ділянки (19 цифр):", reply_markup=ReplyKeyboardRemove())
    return ASK_CADASTER

async def land_cadaster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cad = update.message.text.strip()
    if len(cad.replace(":", "")) != 19:
        await update.message.reply_text("Кадастровий номер має містити 19 цифр. Спробуйте ще раз:")
        return ASK_CADASTER
    context.user_data["cadaster"] = cad
    await update.message.reply_text("Введіть площу ділянки, га:")
    return ASK_AREA

async def land_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        area = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Некоректна площа. Введіть ще раз:")
        return ASK_AREA
    context.user_data["area"] = area
    await update.message.reply_text("Введіть НГО (можна пропустити):")
    return ASK_NGO

async def land_ngo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ngo = float(update.message.text.replace(",", "."))
    except ValueError:
        ngo = None
    context.user_data["ngo"] = ngo
    # Показати вибір поля
    query = sqlalchemy.select(Field)
    fields = await database.fetch_all(query)
    if not fields:
        await update.message.reply_text("Спочатку створіть хоча б одне поле командою ➕ Додати поле!", reply_markup=lands_menu)
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup(
        [[f"{f['id']}: {f['name']}"] for f in fields], resize_keyboard=True
    )
    context.user_data["fields"] = {f"{f['id']}: {f['name']}": f["id"] for f in fields}
    await update.message.reply_text("Оберіть поле для ділянки:", reply_markup=kb)
    return ASK_FIELD

async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_id = context.user_data["fields"].get(update.message.text)
    if not field_id:
        await update.message.reply_text("Оберіть поле зі списку (натисніть кнопку):")
        return ASK_FIELD

    context.user_data["field_id"] = field_id
    keyboard = [[InlineKeyboardButton(c, callback_data=f"csel:{i}")] for i, c in enumerate(COUNCIL_OPTIONS)]
    keyboard.append([InlineKeyboardButton("🔤 Ввести вручну", callback_data="cmanual")])
    await update.message.reply_text(
        "🗺 Оберіть сільську раду:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_COUNCIL

async def council_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    idx = int(query.data.split(":")[1])
    council = COUNCIL_OPTIONS[idx]
    context.user_data["region"] = "Рівненська область"
    context.user_data["district"] = "Рівненський район"
    context.user_data["council"] = council
    await query.answer()
    await query.message.edit_text(f"Обрано: {council}")
    preset = context.user_data.get("preset_payer")
    if preset:
        context.user_data["owner_count"] = 1
        context.user_data["owners"] = [preset]
        return await finalize_land(update, context)
    await query.message.reply_text("Скільки власників має ділянка?")
    return ASK_OWNER_COUNT

async def council_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = ReplyKeyboardMarkup([["Рівненська область"]], resize_keyboard=True)
    await query.message.edit_text("Введіть область:", reply_markup=kb)
    return INPUT_REGION

async def set_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["region"] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["Рівненський район"]], resize_keyboard=True)
    await update.message.reply_text("Введіть район:", reply_markup=kb)
    return INPUT_DISTRICT

async def set_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["district"] = update.message.text.strip()
    await update.message.reply_text("Введіть назву сільради (без скорочень):")
    return INPUT_COUNCIL

async def set_council(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["council"] = update.message.text.strip()
    preset = context.user_data.get("preset_payer")
    if preset:
        context.user_data["owner_count"] = 1
        context.user_data["owners"] = [preset]
        return await finalize_land(update, context)
    await update.message.reply_text("Скільки власників має ділянка?")
    return ASK_OWNER_COUNT

async def set_owner_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введіть число більше 0:")
        return ASK_OWNER_COUNT
    context.user_data["owner_count"] = count
    context.user_data["owners"] = []
    context.user_data["owner_index"] = 1

    payers = await database.fetch_all(sqlalchemy.select(Payer).limit(20))
    if not payers:
        await update.message.reply_text("Спочатку додайте хоча б одного пайовика!", reply_markup=lands_menu)
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup(
        [[f"{p['id']}: {p['name']}"] for p in payers] + [["🔍 Пошук за ПІБ"]], resize_keyboard=True
    )
    context.user_data["payers"] = {f"{p['id']}: {p['name']}": p["id"] for p in payers}
    await update.message.reply_text(
        f"Оберіть власника 1 з {count}:", reply_markup=kb
    )
    return ASK_OWNER

async def select_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔍 Пошук за ПІБ":
        await update.message.reply_text("Введіть частину ПІБ пайовика:")
        return SEARCH_OWNER
    payer_id = context.user_data["payers"].get(text)
    if not payer_id:
        await update.message.reply_text("Оберіть пайовика зі списку (натисніть кнопку):")
        return ASK_OWNER
    context.user_data["owners"].append(payer_id)
    if len(context.user_data["owners"]) < context.user_data["owner_count"]:
        context.user_data["owner_index"] += 1
        await update.message.reply_text(
            f"Оберіть власника {context.user_data['owner_index']} з {context.user_data['owner_count']}:"
        )
        return ASK_OWNER
    return await finalize_land(update, context)
async def search_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    term = update.message.text.strip()
    rows = await database.fetch_all(
        sqlalchemy.select(Payer).where(Payer.c.name.ilike(f"%{term}%")).limit(10)
    )
    if not rows:
        await update.message.reply_text("Нічого не знайдено. Спробуйте ще:")
        return SEARCH_OWNER
    kb = ReplyKeyboardMarkup(
        [[f"{r['id']}: {r['name']}"] for r in rows] + [["◀️ Назад"]],
        resize_keyboard=True,
    )
    context.user_data["search_results"] = {f"{r['id']}: {r['name']}": r["id"] for r in rows}
    await update.message.reply_text("Оберіть пайовика:", reply_markup=kb)
    return CHOOSE_OWNER

async def choose_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "◀️ Назад":
        kb = ReplyKeyboardMarkup(
            [[k] for k in context.user_data["payers"].keys()] + [["🔍 Пошук за ПІБ"]],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            f"Оберіть власника {context.user_data['owner_index']} з {context.user_data['owner_count']}:",
            reply_markup=kb,
        )
        return ASK_OWNER
    payer_id = context.user_data.get("search_results", {}).get(text)
    if not payer_id:
        await update.message.reply_text("Оберіть зі списку або натисніть '◀️ Назад':")
        return CHOOSE_OWNER
    context.user_data["owners"].append(payer_id)
    if len(context.user_data["owners"]) < context.user_data["owner_count"]:
        context.user_data["owner_index"] += 1
        kb = ReplyKeyboardMarkup(
            [[k] for k in context.user_data["payers"].keys()] + [["🔍 Пошук за ПІБ"]],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            f"Оберіть власника {context.user_data['owner_index']} з {context.user_data['owner_count']}:",
            reply_markup=kb,
        )
        return ASK_OWNER
    return await finalize_land(update, context)

async def finalize_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = LandPlot.insert().values(
        cadaster=context.user_data["cadaster"],
        area=context.user_data["area"],
        ngo=context.user_data["ngo"],
        field_id=context.user_data["field_id"],
        payer_id=context.user_data["owners"][0],
        region=context.user_data.get("region"),
        district=context.user_data.get("district"),
        council=context.user_data.get("council"),
    )
    land_id = await database.execute(query)
    share = 1 / context.user_data["owner_count"]
    for pid in context.user_data["owners"]:
        await database.execute(
            LandPlotOwner.insert().values(land_plot_id=land_id, payer_id=pid, share=share)
        )

    context.user_data.clear()
    await prompt_add_docs(
        update,
        context,
        "land",
        land_id,
        "Ділянка додана!",
        lands_menu,
    )
    return ConversationHandler.END


async def start_land_for_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payer_id = int(query.data.split(":")[1])
    await query.answer()
    context.user_data.clear()
    context.user_data["preset_payer"] = payer_id
    await query.message.reply_text(
        "Введіть кадастровий номер ділянки (19 цифр):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_CADASTER

add_land_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^➕ Додати ділянку$"), add_land_start),
        CallbackQueryHandler(start_land_for_payer, pattern=r"^start_land:\d+$"),
    ],
    states={
        ASK_CADASTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_cadaster)],
        ASK_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_area)],
        ASK_NGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, land_ngo)],
        ASK_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_field)],
        CHOOSE_COUNCIL: [
            CallbackQueryHandler(council_chosen, pattern=r"^csel:\d+$"),
            CallbackQueryHandler(council_manual, pattern=r"^cmanual$")
        ],
        INPUT_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_region)],
        INPUT_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_district)],
        INPUT_COUNCIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_council)],
        ASK_OWNER_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_owner_count)],
        ASK_OWNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_owner)],
        SEARCH_OWNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_owner)],
        CHOOSE_OWNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_owner)],
    },
    fallbacks=[]
)

# ==== СПИСОК ДІЛЯНОК ====
async def show_lands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message
    query = sqlalchemy.select(LandPlot)
    lands = await database.fetch_all(query)
    if not lands:
        await msg.reply_text("Ділянки ще не створені.", reply_markup=lands_menu)
        return
    field_ids = {l['field_id'] for l in lands if l['field_id']}
    fields_map = {}
    if field_ids:
        fields = await database.fetch_all(sqlalchemy.select(Field).where(Field.c.id.in_(field_ids)))
        fields_map = {f['id']: f['name'] for f in fields}
    for l in lands:
        fname = fields_map.get(l['field_id'], '—')
        btn = InlineKeyboardButton("Картка", callback_data=f"land_card:{l['id']}")
        await msg.reply_text(
            f"{l['id']}. {l['cadaster']} — {l['area']:.4f} га, поле: {fname}",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )

# --- Картка ділянки ---
async def land_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    land = await database.fetch_one(sqlalchemy.select(LandPlot).where(LandPlot.c.id == land_id))
    field_name = "—"
    owners_txt = "—"
    if land and land['field_id']:
        field = await database.fetch_one(sqlalchemy.select(Field).where(Field.c.id == land['field_id']))
        if field:
            field_name = field['name']
    owners = []
    rows = await database.fetch_all(
        sqlalchemy.select(LandPlotOwner, Payer.c.name).join(Payer, Payer.c.id == LandPlotOwner.c.payer_id).where(
            LandPlotOwner.c.land_plot_id == land_id
        )
    )
    for r in rows:
        owners.append(f"{r['name']} ({r['share']:.2f})")
    if owners:
        owners_txt = ", ".join(owners)
    if not land:
        await query.answer("Ділянка не знайдена!")
        return

    text = (
        f"<b>Картка ділянки</b>\n"
        f"ID: {land['id']}\n"
        f"Кадастр: {land['cadaster']}\n"
        f"Площа: {land['area']:.4f} га\n"
        f"НГО: {land['ngo'] if land['ngo'] else '-'}\n"
        f"Поле: {field_name}\n"
        f"📍 Місце розташування:\n"
        f"{land['council'] or 'не вказано'}, {land['district'] or 'не вказано'}, {land['region'] or 'не вказано'}\n"
        f"Власники: {owners_txt}"
    )

    from crm.events_integration import get_events_text, events_button
    events_block = await get_events_text("land", land_id)
    text += "\n\n" + events_block

    buttons = []
    # --- Додати документи ---
    buttons.append([
        InlineKeyboardButton(
            "📷 Додати документи", callback_data=f"add_docs:land:{land['id']}"
        )
    ])
    # --- Кнопки перегляду/видалення PDF ---
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs)
        .where((UploadedDocs.c.entity_type == "land") & (UploadedDocs.c.entity_id == land_id))
    )
    for doc in docs:
        doc_type = doc['doc_type']
        buttons.append([
            InlineKeyboardButton(f"⬇️ {doc_type}", callback_data=f"send_pdf:{doc['id']}"),
            InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_pdf_db:{doc['id']}")
        ])
    # --- Кнопки власника, інші кнопки ---
    owners_exist = bool(rows)
    if owners_exist:
        buttons.append([InlineKeyboardButton("✏️ Змінити власника", callback_data=f"edit_land_owner:{land['id']}")])
    else:
        buttons.append([InlineKeyboardButton("➕ Додати власника", callback_data=f"edit_land_owner:{land['id']}")])
    buttons.extend([
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit_land:{land['id']}")],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"delete_land:{land['id']}")],
        [events_button("land", land_id)],
        [InlineKeyboardButton("⬅️ До списку", callback_data="to_lands_list")]
    ])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


# ==== ВИДАЛЕННЯ ДІЛЯНКИ ====
async def delete_land_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    from db import get_user_by_tg_id
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == land_id))
    if not land:
        await query.answer("Ділянку не знайдено!", show_alert=True)
        return
    text = (
        f"Ви точно хочете видалити ділянку <b>{land.cadaster}</b>?\n"
        "Цю дію не можна скасувати."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_delete_land:{land_id}")],
        [InlineKeyboardButton("❌ Скасувати", callback_data=f"land_card:{land_id}")],
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

async def delete_land(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    land_id = int(query.data.split(":")[1])
    from db import UploadedDocs, get_user_by_tg_id, log_delete
    user = await get_user_by_tg_id(update.effective_user.id)
    if not user or user["role"] != "admin":
        await query.answer("⛔ У вас немає прав на видалення.", show_alert=True)
        return
    land = await database.fetch_one(LandPlot.select().where(LandPlot.c.id == land_id))
    if not land:
        await query.answer("Ділянку не знайдено!", show_alert=True)
        return
    docs = await database.fetch_all(
        sqlalchemy.select(UploadedDocs).where(
            (UploadedDocs.c.entity_type == "land") & (UploadedDocs.c.entity_id == land_id)
        )
    )
    for d in docs:
        try:
            delete_file_ftp(d["remote_path"])
        except Exception:
            pass
    if docs:
        await database.execute(
            UploadedDocs.delete().where(UploadedDocs.c.id.in_([d["id"] for d in docs]))
        )

    # Remove owners linked to the land plot before deleting the plot itself
    await database.execute(
        LandPlotOwner.delete().where(LandPlotOwner.c.land_plot_id == land_id)
    )

    await database.execute(LandPlot.delete().where(LandPlot.c.id == land_id))
    linked = f"docs:{len(docs)}" if docs else ""
    await log_delete(update.effective_user.id, user["role"], "land", land_id, land.cadaster, linked)
    await query.message.edit_text("✅ Обʼєкт успішно видалено")

# ==== ВИДАЛЕННЯ PDF через FTP ====
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

# ==== СКАЧУВАННЯ PDF через FTP ====
async def send_pdf(update, context):
    query = update.callback_query
    doc_id = int(query.data.split(":")[1])
    row = await database.fetch_one(sqlalchemy.select(UploadedDocs).where(UploadedDocs.c.id == doc_id))
    if row:
        remote_path = row['remote_path']
        filename = to_latin_filename(remote_path.split('/')[-1])
        tmp_path = f"temp_docs/{filename}"
        try:
            os.makedirs("temp_docs", exist_ok=True)
            download_file_ftp(remote_path, tmp_path)
            await query.message.reply_document(document=InputFile(tmp_path), filename=filename)
            os.remove(tmp_path)
        except Exception as e:
            await query.answer(f"Помилка при скачуванні файлу: {e}", show_alert=True)
    else:
        await query.answer("Документ не знайдено!", show_alert=True)

# ==== ПОВЕРНЕННЯ ДО СПИСКУ ====
async def to_lands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_lands(update, context)
