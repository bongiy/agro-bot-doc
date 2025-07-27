import sqlalchemy
from databases import Database
import os

DATABASE_URL = os.getenv("DATABASE_URL")
database = Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

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
