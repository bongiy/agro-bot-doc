from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from datetime import datetime
import os

from db import (
    add_agreement_template, get_agreement_templates, get_agreement_template,
    update_agreement_template, delete_agreement_template
)
from template_vars import TEMPLATE_VARIABLES
from template_utils import (
    extract_variables,
    find_unsupported_vars,
    build_unresolved_message,
)


def _build_all_vars_text() -> str:
    """Return full list of available template variables."""
    sections = []
    for cat in TEMPLATE_VARIABLES.values():
        lines = [f"<code>{v}</code> → {d}" for v, d in cat["items"]]
        sections.append(f"<b>{cat['title']}</b>:\n" + "\n".join(lines))
    return "\n\n".join(sections)
import re
import unicodedata
from ftp_utils import upload_file_ftp, delete_file_ftp

TEMPLATE_TYPES = {
    "rent": "Оренда",
    "emphyteusis": "Емфітевзис",
    "additional": "Додаткова угода",
}

PAYER_TEMPLATE_TYPES = {
    "single": "Один пайовик",
    "multi": "Кілька пайовиків",
}

ALLOWED_VARS = [
    f"{var} — {desc}"
    for cat in TEMPLATE_VARIABLES.values()
    for var, desc in cat["items"]
]

def to_latin_filename(text: str, default: str = "template.docx") -> str:
    name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    name = name.replace(" ", "_")
    name = re.sub(r'[^A-Za-z0-9_.-]', '', name)
    if not name or name.startswith('.docx') or name.lower() == '.docx':
        return default
    if not name.lower().endswith('.docx'):
        name += '.docx'
    return name


ADD_TYPE, ADD_NAME, ADD_FILE, ADD_SCOPE, REPLACE_FILE = range(5)

async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if update.message else update.callback_query.message
    templates = await get_agreement_templates()
    text = "<b>Шаблони договорів</b>:\n"
    if not templates:
        text += "Немає жодного шаблону."
    keyboard = []
    for t in templates:
        status = "✅" if t["is_active"] else "❌"
        t_type = TEMPLATE_TYPES.get(t["type"], t["type"])
        p_type = PAYER_TEMPLATE_TYPES.get(t.get("template_type", "single"), t.get("template_type", "single"))
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {t['name']} ({t_type}, {p_type})",
                callback_data=f"template_card:{t['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("➕ Додати шаблон", callback_data="template_add")])
    keyboard.append([InlineKeyboardButton("📘 Список змінних", callback_data="template_vars")])
    keyboard.append([InlineKeyboardButton("↩️ Адмін-панель", callback_data="admin_panel")])
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def show_templates_cb(update, context):
    await show_templates(update, context)


async def template_vars_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send full list of template variables in one message."""
    text = _build_all_vars_text()
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")

async def template_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    template_id = int(query.data.split(":")[1])
    tmpl = await get_agreement_template(template_id)
    if not tmpl:
        await query.answer("Шаблон не знайдено!", show_alert=True)
        return
    status = "Так" if tmpl["is_active"] else "Ні"
    t_type = TEMPLATE_TYPES.get(tmpl["type"], tmpl["type"])
    p_type = PAYER_TEMPLATE_TYPES.get(tmpl.get("template_type", "single"), tmpl.get("template_type", "single"))
    text = (
        f"<b>{tmpl['name']}</b>\n"
        f"Тип: <code>{t_type}</code>\n"
        f"Пайовики: <code>{p_type}</code>\n"
        f"Активний: <code>{status}</code>"
    )
    kb = [
        [InlineKeyboardButton("♻️ Оновити файл", callback_data=f"template_replace:{template_id}")],
        [InlineKeyboardButton(
            "✅ Увімкнути" if not tmpl["is_active"] else "🚫 Вимкнути",
            callback_data=f"template_toggle:{template_id}"
        )],
        [InlineKeyboardButton("🗑 Видалити", callback_data=f"template_delete:{template_id}")],
        [InlineKeyboardButton("↩️ До списку", callback_data="template_list")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def template_toggle(update, context):
    query = update.callback_query
    template_id = int(query.data.split(":")[1])
    tmpl = await get_agreement_template(template_id)
    if not tmpl:
        await query.answer("Шаблон не знайдено!", show_alert=True)
        return
    new_status = not tmpl["is_active"]
    await update_agreement_template(template_id, {"is_active": new_status})
    await template_card(update, context)

async def template_delete(update, context):
    query = update.callback_query
    template_id = int(query.data.split(":")[1])
    tmpl = await get_agreement_template(template_id)
    if not tmpl:
        await query.answer("Шаблон не знайдено!", show_alert=True)
        return
    if tmpl["file_path"]:
        try:
            delete_file_ftp(tmpl["file_path"])
        except Exception:
            pass
    await delete_agreement_template(template_id)
    await query.answer("Шаблон видалено!")
    await show_templates_cb(update, context)

async def add_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[InlineKeyboardButton(name, callback_data=f"tmpl_type:{key}")] for key, name in TEMPLATE_TYPES.items()]
    keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="template_list")])
    await query.edit_message_text(
        "Оберіть тип шаблону:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_TYPE

async def add_template_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tmpl_type = query.data.split(":")[1]
    context.user_data["tmpl_type"] = tmpl_type
    await query.message.edit_text("Введіть назву шаблону:")
    return ADD_NAME

async def add_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tmpl_name"] = update.message.text.strip()
    vars_text = "\n".join(ALLOWED_VARS)
    await update.message.reply_text(
        "Надішліть файл .docx (до 2MB).\nДопустимі змінні:\n" + vars_text
    )
    return ADD_FILE

async def add_template_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".docx"):
        await update.message.reply_text("Надішліть файл у форматі .docx")
        return ADD_FILE
    if doc.file_size and doc.file_size > 2 * 1024 * 1024:
        await update.message.reply_text("Файл перевищує 2MB. Надішліть менший файл")
        return ADD_FILE
    remote_name = to_latin_filename(doc.file_name)
    tmp_dir = "temp_docs"
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, remote_name)
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(local_path)
    context.user_data["tmpl_local_path"] = local_path
    context.user_data["tmpl_remote_name"] = remote_name
    keyboard = [
        [InlineKeyboardButton("Договору з одним пайовиком", callback_data="tmpl_scope:single")],
        [InlineKeyboardButton("Договору з кількома пайовиками", callback_data="tmpl_scope:multi")],
    ]
    await update.message.reply_text(
        "Цей шаблон призначений для:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ADD_SCOPE


async def add_template_scope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tmpl_scope = query.data.split(":")[1]
    local_path = context.user_data.pop("tmpl_local_path", None)
    remote_name = context.user_data.pop("tmpl_remote_name", "template.docx")
    tmpl_data = {
        "name": context.user_data.get("tmpl_name"),
        "type": context.user_data.get("tmpl_type"),
        "template_type": tmpl_scope,
        "file_path": "",
        "created_at": datetime.utcnow(),
    }
    template_id = await add_agreement_template(tmpl_data)
    remote_path = f"templates/agreements/{template_id}_{remote_name}"
    var_counts = extract_variables(local_path)
    vars_found = {f"{{{{{v}}}}}" for v in var_counts}
    unsupported = find_unsupported_vars(local_path, tmpl_scope)
    upload_file_ftp(local_path, remote_path)
    os.remove(local_path)
    await update_agreement_template(template_id, {"file_path": remote_path})
    allowed = {v for cat in TEMPLATE_VARIABLES.values() for v, _ in cat["items"]}
    used = len([v for v in vars_found if v in allowed])
    await query.message.reply_text(
        f"✅ Шаблон успішно додано\nНазва: {remote_name}\nЗмінні: {used}/{len(allowed)}"
    )
    msg = build_unresolved_message([], unsupported, len(vars_found))
    if msg:
        await query.message.reply_text(msg)
    if tmpl_scope == "multi" and not ({"{{payer.full_name}}", "{{payer.tax_id}}", "{{payer.share}}", "{{loop.index}}"} & vars_found):
        await query.message.reply_text("⚠️ У шаблоні не знайдено циклу для кількох пайовиків")
    context.user_data.pop("tmpl_name", None)
    context.user_data.pop("tmpl_type", None)
    await show_templates(update, context)
    return ConversationHandler.END

async def replace_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    template_id = int(query.data.split(":")[1])
    context.user_data["replace_template_id"] = template_id
    await query.message.reply_text("Надішліть новий файл .docx (до 2MB):")
    return REPLACE_FILE

async def replace_template_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".docx"):
        await update.message.reply_text("Надішліть файл у форматі .docx")
        return REPLACE_FILE
    if doc.file_size and doc.file_size > 2 * 1024 * 1024:
        await update.message.reply_text("Файл перевищує 2MB. Надішліть менший файл")
        return REPLACE_FILE
    template_id = context.user_data.pop("replace_template_id", None)
    if not template_id:
        await update.message.reply_text("Сталася помилка.")
        return ConversationHandler.END
    remote_name = to_latin_filename(doc.file_name)
    remote_path = f"templates/agreements/{template_id}_{remote_name}"
    tmp_dir = "temp_docs"
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, remote_name)
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(local_path)
    var_counts = extract_variables(local_path)
    vars_found = {f"{{{{{v}}}}}" for v in var_counts}
    tmpl = await get_agreement_template(template_id)
    unsupported = find_unsupported_vars(local_path, tmpl["template_type"] if tmpl else None)
    upload_file_ftp(local_path, remote_path)
    os.remove(local_path)
    await update_agreement_template(template_id, {"file_path": remote_path})
    allowed = {v for cat in TEMPLATE_VARIABLES.values() for v, _ in cat["items"]}
    used = len([v for v in vars_found if v in allowed])
    await update.message.reply_text(
        f"✅ Файл оновлено\nЗмінні: {used}/{len(allowed)}"
    )
    msg = build_unresolved_message([], unsupported, len(vars_found))
    if msg:
        await update.message.reply_text(msg)
    await show_templates(update, context)
    return ConversationHandler.END

add_template_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_template_start, pattern=r"^template_add$"),
        MessageHandler(filters.Regex("^➕ Додати шаблон$"), add_template_start)
    ],
    states={
        ADD_TYPE: [CallbackQueryHandler(add_template_type, pattern=r"^tmpl_type:\w+$")],
        ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_template_name)],
        ADD_FILE: [MessageHandler(filters.Document.ALL, add_template_file)],
        ADD_SCOPE: [CallbackQueryHandler(add_template_scope, pattern=r"^tmpl_scope:(single|multi)$")],
    },
    fallbacks=[CallbackQueryHandler(show_templates_cb, pattern=r"^template_list$")]
)

replace_template_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(replace_template_start, pattern=r"^template_replace:\d+$")],
    states={
        REPLACE_FILE: [MessageHandler(filters.Document.ALL, replace_template_file)],
    },
    fallbacks=[CallbackQueryHandler(template_card, pattern=r"^template_card:\d+$")]
)

# Callback handlers for list and item actions
template_card_cb = CallbackQueryHandler(template_card, pattern=r"^template_card:\d+$")
template_toggle_cb = CallbackQueryHandler(template_toggle, pattern=r"^template_toggle:\d+$")
template_delete_cb = CallbackQueryHandler(template_delete, pattern=r"^template_delete:\d+$")
template_list_cb = CallbackQueryHandler(show_templates_cb, pattern=r"^template_list$")
template_vars_cb = MessageHandler(filters.Regex("^📘 Переглянути список змінних$"), template_vars_categories)
template_vars_categories_cb = CallbackQueryHandler(template_vars_categories, pattern=r"^template_vars$")
