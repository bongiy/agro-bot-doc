import sqlalchemy
from databases import Database
from sqlalchemy.dialects.postgresql import JSONB
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
    sqlalchemy.Column("bank_card", sqlalchemy.String),
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
    sqlalchemy.Column("is_deceased", sqlalchemy.Boolean, default=False),
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
    sqlalchemy.Column("region", sqlalchemy.String),
    sqlalchemy.Column("district", sqlalchemy.String),
    sqlalchemy.Column("council", sqlalchemy.String),
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
    sqlalchemy.Column("payer_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id")),
    sqlalchemy.Column("number", sqlalchemy.String(32)),
    sqlalchemy.Column("date_signed", sqlalchemy.DateTime),
    sqlalchemy.Column("date_valid_from", sqlalchemy.DateTime),
    sqlalchemy.Column("date_valid_to", sqlalchemy.DateTime),
    sqlalchemy.Column("duration_years", sqlalchemy.Integer),
    sqlalchemy.Column("rent_amount", sqlalchemy.Numeric(12, 2)),
    sqlalchemy.Column("status", sqlalchemy.String(32), default="signed"),
    sqlalchemy.Column("registration_number", sqlalchemy.String(64)),
    sqlalchemy.Column("registration_date", sqlalchemy.Date),
    sqlalchemy.Column("template_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("agreement_template.id")),
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

# === Звʼязок договір-пайовик (M2M) ===
PayerContract = sqlalchemy.Table(
    "payer_contract",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("contract_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("contract.id")),
    sqlalchemy.Column("payer_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id")),
)

# === Таблиця спадкоємців ===
Heir = sqlalchemy.Table(
    "heir",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "deceased_payer_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("payer.id"),
    ),
    sqlalchemy.Column(
        "heir_payer_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("payer.id"),
    ),
    sqlalchemy.Column("documents", JSONB, default=list),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# === Таблиця передач спадщини ===
InheritanceTransfer = sqlalchemy.Table(
    "inheritance_transfer",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "deceased_payer_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("payer.id"),
    ),
    sqlalchemy.Column(
        "heir_payer_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("payer.id"),
    ),
    sqlalchemy.Column("asset_type", sqlalchemy.String(32)),  # 'land' or 'contract'
    sqlalchemy.Column("asset_id", sqlalchemy.Integer),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
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


# === Heir helpers ===
async def add_heir(deceased_payer_id: int, heir_payer_id: int, documents=None):
    """Create heir record linking deceased and heir payers."""
    data = {
        "deceased_payer_id": deceased_payer_id,
        "heir_payer_id": heir_payer_id,
        "documents": documents or [],
        "created_at": datetime.utcnow(),
    }
    query = Heir.insert().values(**data)
    return await database.execute(query)


async def get_heirs(deceased_payer_id: int):
    """Return heirs for a deceased payer."""
    query = Heir.select().where(Heir.c.deceased_payer_id == deceased_payer_id)
    return await database.fetch_all(query)


async def transfer_assets_to_heir(deceased_payer_id: int, heir_payer_id: int) -> tuple[int, int]:
    """Transfer land plots, contracts and payments from deceased to heir."""
    transferred_land_ids: list[int] = []
    transferred_contract_ids: list[int] = []

    # Transfer land plots ownership
    land_rows = await database.fetch_all(
        sqlalchemy.select(LandPlotOwner.c.land_plot_id).where(
            LandPlotOwner.c.payer_id == deceased_payer_id
        )
    )
    if land_rows:
        transferred_land_ids = [r["land_plot_id"] for r in land_rows]
        await database.execute(
            LandPlotOwner.update()
            .where(LandPlotOwner.c.payer_id == deceased_payer_id)
            .values(payer_id=heir_payer_id)
        )
        await database.execute(
            LandPlot.update()
            .where(
                LandPlot.c.id.in_(transferred_land_ids)
                & (LandPlot.c.payer_id == deceased_payer_id)
            )
            .values(payer_id=heir_payer_id)
        )
        for lid in transferred_land_ids:
            await database.execute(
                InheritanceTransfer.insert().values(
                    deceased_payer_id=deceased_payer_id,
                    heir_payer_id=heir_payer_id,
                    asset_type="land",
                    asset_id=lid,
                    created_at=datetime.utcnow(),
                )
            )

    # Transfer contracts
    contract_rows = await database.fetch_all(
        sqlalchemy.select(PayerContract.c.contract_id)
        .select_from(
            PayerContract.join(
                Contract, PayerContract.c.contract_id == Contract.c.id
            )
        )
        .where(PayerContract.c.payer_id == deceased_payer_id)
        .where(Contract.c.status != "terminated")
    )
    if contract_rows:
        transferred_contract_ids = [r["contract_id"] for r in contract_rows]
        await database.execute(
            PayerContract.update()
            .where(PayerContract.c.payer_id == deceased_payer_id)
            .values(payer_id=heir_payer_id)
        )
        await database.execute(
            Contract.update()
            .where(
                Contract.c.id.in_(transferred_contract_ids)
                & (Contract.c.payer_id == deceased_payer_id)
            )
            .values(payer_id=heir_payer_id)
        )
        for cid in transferred_contract_ids:
            await database.execute(
                InheritanceTransfer.insert().values(
                    deceased_payer_id=deceased_payer_id,
                    heir_payer_id=heir_payer_id,
                    asset_type="contract",
                    asset_id=cid,
                    created_at=datetime.utcnow(),
                )
            )
        # Mark payments
        await database.execute(
            Payment.update()
            .where(Payment.c.agreement_id.in_(transferred_contract_ids))
            .values(notes="Виплата за спадщину")
        )
        if transferred_contract_ids:
            await database.execute(
                InheritanceDebt.update()
                .where(
                    (InheritanceDebt.c.payer_id == deceased_payer_id)
                    & (InheritanceDebt.c.contract_id.in_(transferred_contract_ids))
                    & (InheritanceDebt.c.heir_id.is_(None))
                )
                .values(heir_id=heir_payer_id)
            )

    return len(transferred_land_ids), len(transferred_contract_ids)


async def record_inheritance_debt(payer_id: int):
    """Calculate unpaid rent for active contracts of deceased payer."""
    contracts = await database.fetch_all(
        sqlalchemy.select(Contract.c.id, Contract.c.rent_amount)
        .where(Contract.c.payer_id == payer_id)
        .where(Contract.c.status != "terminated")
    )
    for c in contracts:
        existing = await database.fetch_one(
            sqlalchemy.select(InheritanceDebt)
            .where(InheritanceDebt.c.payer_id == payer_id)
            .where(InheritanceDebt.c.contract_id == c["id"])
        )
        if existing:
            continue
        paid_row = await database.fetch_one(
            sqlalchemy.select(sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.c.amount), 0)).where(
                Payment.c.agreement_id == c["id"]
            )
        )
        paid = float(paid_row[0] if isinstance(paid_row, tuple) else paid_row[0])
        rent = float(c["rent_amount"] or 0)
        if rent > paid:
            await database.execute(
                InheritanceDebt.insert().values(
                    payer_id=payer_id,
                    contract_id=c["id"],
                    amount=rent - paid,
                    date_recorded=datetime.utcnow().date(),
                )
            )


async def settle_inheritance_debt(contract_id: int, payment_id: int, amount: float, notes: str | None = "") -> str:
    """Mark debt as paid if payment covers it and return updated notes."""
    debt = await database.fetch_one(
        sqlalchemy.select(InheritanceDebt)
        .where(InheritanceDebt.c.contract_id == contract_id)
        .where(InheritanceDebt.c.paid == False)
    )
    if debt and amount >= float(debt["amount"]):
        await database.execute(
            InheritanceDebt.update()
            .where(InheritanceDebt.c.id == debt["id"])
            .values(paid=True, payment_id=payment_id)
        )
        prefix = f"{notes}; " if notes else ""
        return prefix + "Виплата боргу"
    return notes or ""

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

# === Таблиця виплат орендної плати ===
Payment = sqlalchemy.Table(
    "payment",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("agreement_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("contract.id")),
    sqlalchemy.Column("amount", sqlalchemy.Numeric(12, 2), nullable=False),
    sqlalchemy.Column("payment_date", sqlalchemy.Date, nullable=False),
    sqlalchemy.Column("payment_type", sqlalchemy.String),
    sqlalchemy.Column("notes", sqlalchemy.String),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# === Таблиця боргів перед спадкоємцями ===
InheritanceDebt = sqlalchemy.Table(
    "inheritance_debt",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("payer_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id")),
    sqlalchemy.Column("heir_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id"), nullable=True),
    sqlalchemy.Column("contract_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("contract.id")),
    sqlalchemy.Column("amount", sqlalchemy.Numeric(12, 2), nullable=False),
    sqlalchemy.Column("date_recorded", sqlalchemy.Date, default=datetime.utcnow),
    sqlalchemy.Column("paid", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("payment_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payment.id"), nullable=True),
)

# === Таблиця потенційних пайовиків ===
PotentialPayer = sqlalchemy.Table(
    "potential_payer",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("full_name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("phone", sqlalchemy.String),
    sqlalchemy.Column("village", sqlalchemy.String),
    sqlalchemy.Column("area_estimate", sqlalchemy.Float),
    sqlalchemy.Column("note", sqlalchemy.String),
    sqlalchemy.Column("status", sqlalchemy.String, default="new"),
    sqlalchemy.Column("last_contact_date", sqlalchemy.Date),
)

# === Таблиця ділянок потенційних пайовиків ===
PotentialLandPlot = sqlalchemy.Table(
    "potential_land_plot",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "potential_payer_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("potential_payer.id"),
    ),
    sqlalchemy.Column("cadastre", sqlalchemy.String(25)),
    sqlalchemy.Column("area", sqlalchemy.Float),
)

# === Таблиця звернень пайовиків ===
PayerRequest = sqlalchemy.Table(
    "payer_requests",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("payer_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payer.id")),
    sqlalchemy.Column("type", sqlalchemy.String),
    sqlalchemy.Column("description", sqlalchemy.String),
    sqlalchemy.Column("date_submitted", sqlalchemy.Date),
    sqlalchemy.Column("status", sqlalchemy.String),
    sqlalchemy.Column("document_path", sqlalchemy.String),
    sqlalchemy.Column("responsible_user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("user.id")),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# === Таблиця подій CRM ===
CRMEvent = sqlalchemy.Table(
    "crm_events",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("entity_type", sqlalchemy.String),
    sqlalchemy.Column("entity_id", sqlalchemy.Integer),
    sqlalchemy.Column("event_datetime", sqlalchemy.DateTime),
    sqlalchemy.Column("event_type", sqlalchemy.String),
    sqlalchemy.Column("comment", sqlalchemy.String),
    sqlalchemy.Column("responsible_user_id", sqlalchemy.BigInteger, nullable=False),
    sqlalchemy.Column("status", sqlalchemy.String, default="planned"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
    sqlalchemy.Column("created_by_user_id", sqlalchemy.BigInteger),
    sqlalchemy.Column("reminder_status", JSONB, default=dict),
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
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "land_plot" ADD COLUMN IF NOT EXISTS region VARCHAR'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "land_plot" ADD COLUMN IF NOT EXISTS district VARCHAR'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "land_plot" ADD COLUMN IF NOT EXISTS council VARCHAR'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "payer" ADD COLUMN IF NOT EXISTS bank_card VARCHAR'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "payer" ADD COLUMN IF NOT EXISTS is_deceased BOOLEAN DEFAULT FALSE'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "contract" ADD COLUMN IF NOT EXISTS rent_amount NUMERIC(12,2)'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "contract" ADD COLUMN IF NOT EXISTS payer_id INTEGER REFERENCES payer(id)'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "contract" ADD COLUMN IF NOT EXISTS status VARCHAR'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "contract" ADD COLUMN IF NOT EXISTS registration_number VARCHAR'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "contract" ADD COLUMN IF NOT EXISTS registration_date DATE'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "contract" ADD COLUMN IF NOT EXISTS template_id INTEGER REFERENCES agreement_template(id)'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "crm_events" ADD COLUMN IF NOT EXISTS event_datetime TIMESTAMP'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "crm_events" ADD COLUMN IF NOT EXISTS created_by_user_id BIGINT'
    ))
    conn.execute(sqlalchemy.text(
        "ALTER TABLE \"crm_events\" ADD COLUMN IF NOT EXISTS reminder_status JSONB DEFAULT '{}'::jsonb"
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "crm_events" ADD COLUMN IF NOT EXISTS responsible_user_id BIGINT NOT NULL DEFAULT 0'
    ))
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "payer_requests" ADD COLUMN IF NOT EXISTS responsible_user_id INTEGER REFERENCES "user"(id)'
    ))

