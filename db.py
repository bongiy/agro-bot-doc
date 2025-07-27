import sqlalchemy
from databases import Database
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
database = Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()
engine = sqlalchemy.create_engine(DATABASE_URL)

# === Таблиця пайовика ===
Payer = sqlalchemy.Table(
    "payer",  # Таблиця в однині!
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("ipn", sqlalchemy.String(10)),
    sqlalchemy.Column("oblast", sqlalchemy.String),
    sqlalchemy.Column("rayon", sqlalchemy.String),
    sqlalchemy.Column("selo", sqlalchemy.String),
    sqlalchemy.Column("vul", sqlalchemy.String),
    sqlalchemy.Column("bud", sqlalchemy.String),
    sqlalchemy.Column("kv", sqlalchemy.String),
    sqlalchemy.Column("phone", sqlalchemy.String),
    sqlalchemy.Column("doc_type", sqlalchemy.String),
    sqlalchemy.Column("passport_series", sqlalchemy.String),
    sqlalchemy.Column("passport_number", sqlalchemy.String),
    sqlalchemy.Column("passport_issuer", sqlalchemy.String),
    sqlalchemy.Column("passport_date", sqlalchemy.String),
    sqlalchemy.Column("id_number", sqlalchemy.String),
    sqlalchemy.Column("unzr", sqlalchemy.String),
    sqlalchemy.Column("idcard_issuer", sqlalchemy.String),
    sqlalchemy.Column("idcard_date", sqlalchemy.String),
    sqlalchemy.Column("birth_date", sqlalchemy.String),
)

# === Таблиця Поле ===
Field = sqlalchemy.Table(
    "field",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(100), unique=True, nullable=False),
    sqlalchemy.Column("area_actual", sqlalchemy.Float, nullable=False),
)

# === Таблиця Ділянка ===
LandPlot = sqlalchemy.Table(
    "land_plot",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("cadaster", sqlalchemy.String(25), unique=True, nullable=False),
    sqlalchemy.Column("area", sqlalchemy.Float, nullable=False),
    sqlalchemy.Column("ngo", sqlalchemy.Float),  # можна null
    sqlalchemy.Column("field_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("field.id")),  # зв'язок з полем
    sqlalchemy.Column("payer_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id"), nullable=True),  # <-- ДОДАЙ ЦЕ!
)

# === Таблиця власників ділянок ===
LandPlotOwner = sqlalchemy.Table(
    "land_plot_owner",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("land_plot_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("land_plot.id")),
    sqlalchemy.Column("payer_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id")),
    sqlalchemy.Column("share", sqlalchemy.Float),
)

# === Таблиця договорів оренди ===
Contract = sqlalchemy.Table(
    "contract",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("company_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("company.id")),
    sqlalchemy.Column("number", sqlalchemy.String(32)),
    sqlalchemy.Column("date_signed", sqlalchemy.DateTime),
    sqlalchemy.Column("date_valid_from", sqlalchemy.DateTime),
    sqlalchemy.Column("date_valid_to", sqlalchemy.DateTime),
    sqlalchemy.Column("duration_years", sqlalchemy.Integer),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime, onupdate=datetime.utcnow),
    sqlalchemy.UniqueConstraint("company_id", "number", name="uq_contract_number"),
)

# === Звʼязок контракт-ділянка (M2M) ===
ContractLandPlot = sqlalchemy.Table(
    "contract_land_plot",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("contract_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("contract.id")),
    sqlalchemy.Column("land_plot_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("land_plot.id")),
)

# === FTP FILES ===
UploadedDocs = sqlalchemy.Table(
    "uploaded_docs",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("entity_type", sqlalchemy.String(32)),  # 'payer_passport', 'land', 'contract'
    sqlalchemy.Column("entity_id", sqlalchemy.Integer),
    sqlalchemy.Column("doc_type", sqlalchemy.String(64)),
    sqlalchemy.Column("remote_path", sqlalchemy.String(255)),
)

# === Таблиця ТОВ ===
Company = sqlalchemy.Table(
    "company", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("opf", sqlalchemy.String(16)),                # нове поле
    sqlalchemy.Column("full_name", sqlalchemy.String(255)),         # нове поле
    sqlalchemy.Column("short_name", sqlalchemy.String(128)),        # нове поле
    sqlalchemy.Column("name", sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column("edrpou", sqlalchemy.String(10), nullable=False, unique=True),
    sqlalchemy.Column("bank_account", sqlalchemy.String(34)),
    sqlalchemy.Column("tax_group", sqlalchemy.String(32)),
    sqlalchemy.Column("is_vat_payer", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("vat_ipn", sqlalchemy.String(12)),
    sqlalchemy.Column("address_legal", sqlalchemy.String(255)),
    sqlalchemy.Column("address_postal", sqlalchemy.String(255)),
    sqlalchemy.Column("director", sqlalchemy.String(128)),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime),
)

async def add_company(data: dict):
    query = Company.insert().values(**data)
    return await database.execute(query)

async def get_companies():
    query = Company.select().order_by(Company.c.name)
    return await database.fetch_all(query)

async def get_company(company_id: int):
    query = Company.select().where(Company.c.id == company_id)
    return await database.fetch_one(query)

async def update_company(company_id: int, data: dict):
    query = Company.update().where(Company.c.id == company_id).values(**data)
    await database.execute(query)

async def delete_company(company_id: int):
    query = Company.delete().where(Company.c.id == company_id)
    await database.execute(query)

# === Таблиця користувачів ===
User = sqlalchemy.Table(
    "user",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("telegram_id", sqlalchemy.BigInteger, unique=True),
    sqlalchemy.Column("full_name", sqlalchemy.String(255)),
    sqlalchemy.Column("username", sqlalchemy.String(255)),
    sqlalchemy.Column("role", sqlalchemy.String(10), default="user"),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# === Таблиця логів адміністрування ===
AdminAction = sqlalchemy.Table(
    "admin_action",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("admin_id", sqlalchemy.BigInteger),
    sqlalchemy.Column("action", sqlalchemy.String(255)),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# === Таблиця логів видалення ===
DeleteLog = sqlalchemy.Table(
    "delete_log",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("admin_id", sqlalchemy.BigInteger),
    sqlalchemy.Column("role", sqlalchemy.String(10)),
    sqlalchemy.Column("entity_type", sqlalchemy.String(64)),
    sqlalchemy.Column("entity_id", sqlalchemy.Integer),
    sqlalchemy.Column("name", sqlalchemy.String(255)),
    sqlalchemy.Column("linked_info", sqlalchemy.String(255)),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# === Шаблони договорів ===
AgreementTemplate = sqlalchemy.Table(
    "agreement_template",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(255)),
    sqlalchemy.Column("type", sqlalchemy.String(32)),
    sqlalchemy.Column("file_path", sqlalchemy.String(255)),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

async def add_user(
    tg_id: int,
    username: str | None = None,
    role: str = "user",
    full_name: str | None = None,
):
    query = User.insert().values(
        telegram_id=tg_id,
        username=username,
        full_name=full_name,
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    return await database.execute(query)

async def get_user_by_tg_id(tg_id: int):
    query = User.select().where(User.c.telegram_id == tg_id)
    return await database.fetch_one(query)

async def get_users(role: str | None = None, is_active: bool | None = None):
    query = User.select()
    if role:
        query = query.where(User.c.role == role)
    if is_active is not None:
        query = query.where(User.c.is_active == is_active)
    query = query.order_by(User.c.id)
    return await database.fetch_all(query)

async def update_user(tg_id: int, data: dict):
    query = User.update().where(User.c.telegram_id == tg_id).values(**data)
    await database.execute(query)

async def log_admin_action(admin_id: int, action: str):
    query = AdminAction.insert().values(
        admin_id=admin_id,
        action=action,
        created_at=datetime.utcnow(),
    )
    await database.execute(query)

async def log_delete(admin_id: int, role: str, entity_type: str, entity_id: int | None, name: str, linked_info: str = ""):
    query = DeleteLog.insert().values(
        admin_id=admin_id,
        role=role,
        entity_type=entity_type,
        entity_id=entity_id,
        name=name,
        linked_info=linked_info,
        created_at=datetime.utcnow(),
    )
    await database.execute(query)

# === Agreement Template helpers ===
async def add_agreement_template(data: dict):
    query = AgreementTemplate.insert().values(**data)
    return await database.execute(query)

async def get_agreement_templates(active_only: bool | None = None):
    query = AgreementTemplate.select()
    if active_only is not None:
        query = query.where(AgreementTemplate.c.is_active == active_only)
    query = query.order_by(AgreementTemplate.c.id)
    return await database.fetch_all(query)

async def get_agreement_template(template_id: int):
    query = AgreementTemplate.select().where(AgreementTemplate.c.id == template_id)
    return await database.fetch_one(query)

async def update_agreement_template(template_id: int, data: dict):
    query = AgreementTemplate.update().where(AgreementTemplate.c.id == template_id).values(**data)
    await database.execute(query)

async def delete_agreement_template(template_id: int):
    query = AgreementTemplate.delete().where(AgreementTemplate.c.id == template_id)
    await database.execute(query)

async def ensure_admin(tg_id: int, username: str | None = None):
    """Ensure a user exists with admin role and is active."""
    user = await get_user_by_tg_id(tg_id)
    if not user:
        await add_user(tg_id, username=username, role="admin")
        return
    update_data = {}
    if user["role"] != "admin":
        update_data["role"] = "admin"
    if not user["is_active"]:
        update_data["is_active"] = True
    if update_data:
        await update_user(tg_id, update_data)

# Create all tables if they do not exist.
metadata.create_all(engine)

# Ensure new columns exist for older databases
with engine.begin() as conn:
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)'
    ))

