import sqlalchemy
from databases import Database
import os

# Заміни цю стрічку своїм підключенням або використовуй os.environ
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:wnGUJjAIHWwemQmPPoOgESnyRBmgRsYw@tramway.proxy.rlwy.net:58771/railway")

database = Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

Payer = sqlalchemy.Table(
    "payer",  # Тільки однина!
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(255)),
    sqlalchemy.Column("ipn", sqlalchemy.String(10)),
    sqlalchemy.Column("oblast", sqlalchemy.String(100)),
    sqlalchemy.Column("rayon", sqlalchemy.String(100)),
    sqlalchemy.Column("selo", sqlalchemy.String(100)),
    sqlalchemy.Column("vul", sqlalchemy.String(100)),
    sqlalchemy.Column("bud", sqlalchemy.String(20)),
    sqlalchemy.Column("kv", sqlalchemy.String(20)),
    sqlalchemy.Column("phone", sqlalchemy.String(20)),
    sqlalchemy.Column("doc_type", sqlalchemy.String(20)),
    sqlalchemy.Column("passport_series", sqlalchemy.String(10)),
    sqlalchemy.Column("passport_number", sqlalchemy.String(10)),
    sqlalchemy.Column("passport_issuer", sqlalchemy.String(255)),
    sqlalchemy.Column("passport_date", sqlalchemy.String(20)),
    sqlalchemy.Column("id_number", sqlalchemy.String(20)),
    sqlalchemy.Column("unzr", sqlalchemy.String(20)),
    sqlalchemy.Column("idcard_issuer", sqlalchemy.String(10)),
    sqlalchemy.Column("idcard_date", sqlalchemy.String(20)),
    sqlalchemy.Column("birth_date", sqlalchemy.String(20)),
)

# Можеш додати цю функцію для ініціалізації (створення таблиці, якщо вона відсутня)
async def create_tables():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.create_all(engine)
