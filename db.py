import os
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date
from databases import Database

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Railway може давати postgres:// замість postgresql://, а asyncpg хоче postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

database = Database(DATABASE_URL)
Base = declarative_base()

class Payer(Base):
    __tablename__ = "payers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ipn = Column(String(10), nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String(20), nullable=False)
    doc_type = Column(String, nullable=False)
    passport_series = Column(String(2))
    passport_number = Column(String(6))
    passport_issuer = Column(String)
    passport_date = Column(String(10))
    id_number = Column(String(9))
    unzr = Column(String(14))
    idcard_issuer = Column(String(4))
    idcard_date = Column(String(10))
    birth_date = Column(String(10))
