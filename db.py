import sqlalchemy
from databases import Database
import os

DATABASE_URL = os.getenv("DATABASE_URL")
database = Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

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
