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
from ftp_utils import upload_file_ftp, delete_file_ftp

TEMPLATE_TYPES = {
    "rent": "Оренда",
    "emphyteusis": "Емфітевзис",
    "additional": "Додаткова угода",
}

ALLOWED_VARS = [
    f"{var} — {desc}"
    for cat in TEMPLATE_VARIABLES.values()
    for var, desc in cat["items"]
]

ADD_TYPE, ADD_NAME, ADD_FILE, REPLACE_FILE = range(4)

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
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {t['name']} ({t_type})",
                callback_data=f"template_card:{t['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("➕ Додати шаблон", callback_data="template_add")])
    keyboard.append([InlineKeyboardButton("📘 Список змінних", callback_data="template_vars")])
    keyboard.append([InlineKeyboardButton("↩️ Адмінпанель", callback_data="admin_panel")])
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def show_templates_cb(update, context):
    await show_templates(update, context)


async def template_vars_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of template variable categories."""
    text = "<b>Список змінних</b>\nОберіть категорію:"
    keyboard = [
        [InlineKeyboardButton(cat["title"], callback_data=f"varcat:{key}")]
        for key, cat in TEMPLATE_VARIABLES.items()
    ]
    keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="template_list")])
    msg = update.callback_query if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )


def _build_vars_text(cat_key: str) -> str:
    cat = TEMPLATE_VARIABLES[cat_key]
    lines = [f"<code>{v}</code> — {d}" for v, d in cat["items"]]
    return f"<b>{cat['title']}</b>\n" + "\n".join(lines)


async def template_vars_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cat_key = query.data.split(":")[1]
    text = _build_vars_text(cat_key)
    keyboard = [
        [InlineKeyboardButton("📋 Копіювати", callback_data=f"copyvar:{v}")]
        for v, _ in TEMPLATE_VARIABLES[cat_key]["items"]
    ]
    keyboard.append([InlineKeyboardButton("↩️ Категорії", callback_data="template_vars")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def copy_variable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    var = query.data.split(":", 1)[1]
    await query.answer()
    await query.message.reply_text(f"<code>{var}</code>", parse_mode="HTML")

async def template_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    template_id = int(query.data.split(":")[1])
    tmpl = await get_agreement_template(template_id)
    if not tmpl:
        await query.answer("Шаблон не знайдено!", show_alert=True)
        return
    status = "Так" if tmpl["is_active"] else "Ні"
    t_type = TEMPLATE_TYPES.get(tmpl["type"], tmpl["type"])
    text = (
        f"<b>{tmpl['name']}</b>\n"
        f"Тип: <code>{t_type}</code>\n"
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
    tmpl_data = {
        "name": context.user_data["tmpl_name"],
        "type": context.user_data["tmpl_type"],
        "file_path": "",
        "created_at": datetime.utcnow(),
    }
    template_id = await add_agreement_template(tmpl_data)
    remote_path = f"templates/agreements/{template_id}.docx"
    tmp_dir = "temp_docs"
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, f"{template_id}.docx")
    await doc.get_file().download_to_drive(local_path)
    upload_file_ftp(local_path, remote_path)
    os.remove(local_path)
    await update_agreement_template(template_id, {"file_path": remote_path})
    await update.message.reply_text("✅ Шаблон збережено")
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
    remote_path = f"templates/agreements/{template_id}.docx"
    tmp_dir = "temp_docs"
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, f"{template_id}.docx")
    await doc.get_file().download_to_drive(local_path)
    upload_file_ftp(local_path, remote_path)
    os.remove(local_path)
    await update_agreement_template(template_id, {"file_path": remote_path})
    await update.message.reply_text("✅ Файл оновлено")
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
template_var_list_cb = CallbackQueryHandler(template_vars_list, pattern=r"^varcat:\w+$")
copy_var_cb = CallbackQueryHandler(copy_variable, pattern=r"^copyvar:.+")
