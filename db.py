import sqlalchemy
from databases import Database
from sqlalchemy.dialects.postgresql import JSONB
import os
from datetime import datetime, date
from utils.contacts import normalize_phone, normalize_edrpou

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

# === Таблиця суборенди ===
Sublease = sqlalchemy.Table(
    "sublease",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("land_plot_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("land_plot.id")),
    sqlalchemy.Column("from_company_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("company.id")),
    sqlalchemy.Column("to_company_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("company.id")),
    sqlalchemy.Column(
        "counterparty_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("counterparty.id"),
        nullable=True,
    ),
    sqlalchemy.Column("date_from", sqlalchemy.Date),
    sqlalchemy.Column("date_to", sqlalchemy.Date),
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

# === Таблиця контрагентів ===
Counterparty = sqlalchemy.Table(
    "counterparty",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column("edrpou", sqlalchemy.String(8), nullable=False, unique=True),
    sqlalchemy.Column("director", sqlalchemy.String(255)),
    sqlalchemy.Column("legal_address", sqlalchemy.String(255)),
    sqlalchemy.Column("phone", sqlalchemy.String(13)),
    sqlalchemy.Column("email", sqlalchemy.String(255)),
    sqlalchemy.Column("note", sqlalchemy.Text),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
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


# === Counterparty helpers ===
async def add_counterparty(data: dict):
    data = data.copy()
    if "phone" in data:
        data["phone"] = normalize_phone(data["phone"])
    if "edrpou" in data:
        data["edrpou"] = normalize_edrpou(data["edrpou"])
    query = Counterparty.insert().values(**data)
    return await database.execute(query)


async def get_counterparty(counterparty_id: int):
    query = Counterparty.select().where(Counterparty.c.id == counterparty_id)
    return await database.fetch_one(query)


async def get_counterparties():
    query = Counterparty.select().order_by(Counterparty.c.name)
    return await database.fetch_all(query)


async def search_counterparties(query_str: str):
    like = f"%{query_str}%"
    query = (
        Counterparty.select()
        .where(
            (Counterparty.c.name.ilike(like))
            | (Counterparty.c.edrpou == query_str)
            | (Counterparty.c.director.ilike(like))
        )
        .order_by(Counterparty.c.name)
    )
    return await database.fetch_all(query)


async def update_counterparty(counterparty_id: int, data: dict):
    data = data.copy()
    if "phone" in data:
        data["phone"] = normalize_phone(data["phone"])
    if "edrpou" in data:
        data["edrpou"] = normalize_edrpou(data["edrpou"])
    query = (
        Counterparty.update()
        .where(Counterparty.c.id == counterparty_id)
        .values(**data)
    )
    await database.execute(query)


async def delete_counterparty(counterparty_id: int):
    query = Counterparty.delete().where(Counterparty.c.id == counterparty_id)
    await database.execute(query)


# === Sublease helpers ===
async def add_sublease(data: dict):
    """Create a sublease record."""
    query = Sublease.insert().values(**data)
    return await database.execute(query)


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


async def get_payment_report_rows(
    start_date: date | None = None,
    end_date: date | None = None,
    payer_query: str | None = None,
    company_query: str | None = None,
    status: str | None = None,
    heirs_only: bool = False,
    limit: int | None = None,
    offset: int = 0,
):
    """Return payment rows with optional filters for reports."""
    heir_condition = (
        (InheritanceDebt.c.payment_id.isnot(None))
        | Payment.c.notes.ilike("%спад%")
        | Payment.c.notes.ilike("%борг%")
    )

    status_case = sqlalchemy.case(
        (Payment.c.status == "pending", "Очікує"),
        (Payment.c.status == "partial", "Частково"),
        (heir_condition, "Виплата спадкоємцю"),
        else_="Виплачено",
    ).label("status")
    heir_flag = sqlalchemy.case((heir_condition, True), else_=False).label("is_heir")

    query = (
        sqlalchemy.select(
            Payment.c.id,
            Payment.c.payment_date,
            Payment.c.amount,
            Payer.c.name.label("payer_name"),
            Company.c.name.label("company_name"),
            status_case,
            heir_flag,
        )
        .select_from(Payment)
        .join(Contract, Contract.c.id == Payment.c.agreement_id)
        .join(Payer, Payer.c.id == Contract.c.payer_id)
        .join(Company, Company.c.id == Contract.c.company_id)
        .outerjoin(InheritanceDebt, InheritanceDebt.c.payment_id == Payment.c.id)
    )

    filters = []
    if start_date:
        filters.append(Payment.c.payment_date >= start_date)
    if end_date:
        filters.append(Payment.c.payment_date <= end_date)
    if payer_query:
        filters.append(
            (Payer.c.name.ilike(f"%{payer_query}%"))
            | (Payer.c.unzr == payer_query)
        )
    if company_query:
        filters.append(
            (Company.c.name.ilike(f"%{company_query}%"))
            | (Company.c.short_name.ilike(f"%{company_query}%"))
        )
    if status == "heir":
        filters.append(heir_condition)
    elif status == "paid":
        filters.append(
            sqlalchemy.and_(
                ~heir_condition,
                sqlalchemy.or_(
                    Payment.c.status.is_(None),
                    Payment.c.status == "paid",
                ),
            )
        )
    elif status in {"pending", "partial"}:
        filters.append(Payment.c.status == status)
    if heirs_only:
        filters.append(heir_condition)
    filters.append(Contract.c.date_valid_from <= datetime.utcnow())
    if filters:
        query = query.where(sqlalchemy.and_(*filters))

    query = query.order_by(Payment.c.payment_date.desc())
    if limit is not None:
        query = query.limit(limit).offset(offset)
    rows = await database.fetch_all(query)
    return rows


async def get_rent_summary(
    year: int,
    company_query: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """Return aggregated rent payment info per company."""
    payments_sub = (
        sqlalchemy.select(
            Payment.c.agreement_id.label("cid"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.c.amount), 0).label("paid"),
        )
        .where(sqlalchemy.extract("year", Payment.c.payment_date) == year)
        .group_by(Payment.c.agreement_id)
        .subquery()
    )

    contract_active = sqlalchemy.and_(
        Contract.c.date_valid_from <= datetime.utcnow(),
        sqlalchemy.extract("year", Contract.c.date_valid_from) <= year,
        sqlalchemy.or_(
            Contract.c.date_valid_to.is_(None),
            sqlalchemy.extract("year", Contract.c.date_valid_to) >= year,
        ),
    )

    status_expr = sqlalchemy.case(
        (sqlalchemy.func.coalesce(payments_sub.c.paid, 0) >= Contract.c.rent_amount, "paid"),
        (sqlalchemy.func.coalesce(payments_sub.c.paid, 0) > 0, "partial"),
        else_="pending",
    )
    contract_base = (
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.company_id,
            Contract.c.payer_id,
            Contract.c.rent_amount,
            sqlalchemy.func.coalesce(payments_sub.c.paid, 0).label("paid"),
            status_expr.label("status"),
        )
        .select_from(Contract)
        .outerjoin(payments_sub, payments_sub.c.cid == Contract.c.id)
        .where(contract_active)
    )

    if company_query:
        contract_base = contract_base.join(Company, Company.c.id == Contract.c.company_id)
        contract_base = contract_base.where(
            (Company.c.name.ilike(f"%{company_query}%"))
            | (Company.c.short_name.ilike(f"%{company_query}%"))
        )
    if status in {"pending", "partial", "paid"}:
        contract_base = contract_base.where(status_expr == status)

    contract_base = contract_base.subquery()

    query = (
        sqlalchemy.select(
            Company.c.name,
            sqlalchemy.func.count(sqlalchemy.distinct(contract_base.c.id)).label("contracts"),
            sqlalchemy.func.count(sqlalchemy.distinct(contract_base.c.payer_id)).label("payers"),
            sqlalchemy.func.count(sqlalchemy.distinct(ContractLandPlot.c.land_plot_id)).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.rent_amount), 0).label("rent_total"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.paid), 0).label("paid_total"),
            sqlalchemy.func.coalesce(
                sqlalchemy.func.sum(
                    sqlalchemy.case(
                        (contract_base.c.status == "pending", contract_base.c.rent_amount),
                        else_=0,
                    )
                ),
                0,
            ).label("pending_amount"),
            sqlalchemy.func.coalesce(
                sqlalchemy.func.sum(
                    sqlalchemy.case(
                        (contract_base.c.status == "partial", contract_base.c.rent_amount),
                        else_=0,
                    )
                ),
                0,
            ).label("partial_amount"),
            sqlalchemy.func.coalesce(
                sqlalchemy.func.sum(
                    sqlalchemy.case(
                        (contract_base.c.status == "paid", contract_base.c.rent_amount),
                        else_=0,
                    )
                ),
                0,
            ).label("paid_amount"),
        )
        .select_from(contract_base)
        .join(Company, Company.c.id == contract_base.c.company_id)
        .outerjoin(ContractLandPlot, ContractLandPlot.c.contract_id == contract_base.c.id)
        .group_by(Company.c.id)
        .order_by(Company.c.name)
    )

    if limit is not None:
        query = query.limit(limit).offset(offset)

    rows = await database.fetch_all(query)
    return rows

# === Узагальнений звіт по ділянках ===
async def get_land_overview():
    """Return aggregated land plot statistics."""
    total = await database.fetch_one(
        sqlalchemy.select(
            sqlalchemy.func.count(LandPlot.c.id).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.ngo), 0).label("ngo"),
        )
    )

    payer_count = await database.fetch_val(
        sqlalchemy.select(
            sqlalchemy.func.count(sqlalchemy.distinct(LandPlotOwner.c.payer_id))
        )
    )
    contract_count = await database.fetch_val(
        sqlalchemy.select(
            sqlalchemy.func.count(sqlalchemy.distinct(Contract.c.id))
        ).where(Contract.c.status != "terminated")
    )
    company_count = await database.fetch_val(
        sqlalchemy.select(
            sqlalchemy.func.count(sqlalchemy.distinct(Contract.c.company_id))
        ).where(Contract.c.status != "terminated")
    )

    fields = await database.fetch_all(
        sqlalchemy.select(
            Field.c.name.label("name"),
            sqlalchemy.func.count(LandPlot.c.id).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .outerjoin(LandPlot, LandPlot.c.field_id == Field.c.id)
        .group_by(Field.c.id)
        .order_by(Field.c.name)
    )

    companies = await database.fetch_all(
        sqlalchemy.select(
            Company.c.name.label("name"),
            sqlalchemy.func.count(sqlalchemy.distinct(LandPlot.c.id)).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .select_from(Company)
        .join(Contract, sqlalchemy.and_(Contract.c.company_id == Company.c.id, Contract.c.status != "terminated"))
        .join(ContractLandPlot, ContractLandPlot.c.contract_id == Contract.c.id)
        .join(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .group_by(Company.c.id)
        .order_by(Company.c.name)
    )

    contracts = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.number.label("number"),
            sqlalchemy.func.count(LandPlot.c.id).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .select_from(Contract)
        .join(ContractLandPlot, ContractLandPlot.c.contract_id == Contract.c.id)
        .join(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .where(Contract.c.status != "terminated")
        .group_by(Contract.c.id)
        .order_by(Contract.c.number)
    )

    with_contract = await database.fetch_one(
        sqlalchemy.select(
            sqlalchemy.func.count(sqlalchemy.distinct(LandPlot.c.id)).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .select_from(LandPlot)
        .join(ContractLandPlot, ContractLandPlot.c.land_plot_id == LandPlot.c.id)
        .join(Contract, sqlalchemy.and_(Contract.c.id == ContractLandPlot.c.contract_id, Contract.c.status != "terminated"))
    )
    without_plots = total["plots"] - (with_contract["plots"] or 0)
    without_area = float(total["area"] or 0) - float(with_contract["area"] or 0)
    statuses = [
        {
            "status": "with_contract",
            "plots": with_contract["plots"] or 0,
            "area": float(with_contract["area"] or 0),
        },
        {"status": "without_contract", "plots": without_plots, "area": without_area},
    ]

    summary = {
        "plots": total["plots"] or 0,
        "area": float(total["area"] or 0),
        "ngo": float(total["ngo"] or 0),
        "payers": payer_count or 0,
        "contracts": contract_count or 0,
        "companies": company_count or 0,
    }

    return summary, fields, companies, statuses, contracts


# === Статистика по полях ===
async def get_fields_report():
    """Return statistics for each field including physical area and coverage."""

    plots_sub = (
        sqlalchemy.select(
            LandPlot.c.field_id.label("field_id"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("plots_area"),
            sqlalchemy.func.count(
                sqlalchemy.distinct(LandPlotOwner.c.payer_id)
            ).label("payers"),
        )
        .select_from(LandPlot)
        .outerjoin(LandPlotOwner, LandPlotOwner.c.land_plot_id == LandPlot.c.id)
        .group_by(LandPlot.c.field_id)
        .subquery()
    )

    contract_sub = (
        sqlalchemy.select(
            LandPlot.c.field_id.label("field_id"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label(
                "contract_area"
            ),
            sqlalchemy.func.coalesce(
                sqlalchemy.func.sum(Contract.c.rent_amount), 0
            ).label("rent_sum"),
        )
        .select_from(LandPlot)
        .join(ContractLandPlot, ContractLandPlot.c.land_plot_id == LandPlot.c.id)
        .join(
            Contract,
            sqlalchemy.and_(
                Contract.c.id == ContractLandPlot.c.contract_id,
                Contract.c.status != "terminated",
            ),
        )
        .group_by(LandPlot.c.field_id)
        .subquery()
    )

    rows = await database.fetch_all(
        sqlalchemy.select(
            Field.c.name.label("name"),
            Field.c.area_actual.label("physical_area"),
            sqlalchemy.func.coalesce(plots_sub.c.plots_area, 0).label("plots_area"),
            sqlalchemy.func.coalesce(contract_sub.c.contract_area, 0).label(
                "contract_area"
            ),
            (
                sqlalchemy.func.coalesce(plots_sub.c.plots_area, 0)
                - sqlalchemy.func.coalesce(contract_sub.c.contract_area, 0)
            ).label("without_contract"),
            sqlalchemy.case(
                (
                    Field.c.area_actual != 0,
                    sqlalchemy.func.coalesce(contract_sub.c.contract_area, 0)
                    / Field.c.area_actual
                    * 100,
                ),
                else_=0,
            ).label("coverage"),
            sqlalchemy.func.coalesce(plots_sub.c.payers, 0).label("payers"),
            sqlalchemy.func.coalesce(contract_sub.c.rent_sum, 0).label("rent_sum"),
        )
        .select_from(Field)
        .outerjoin(plots_sub, plots_sub.c.field_id == Field.c.id)
        .outerjoin(contract_sub, contract_sub.c.field_id == Field.c.id)
        .order_by(Field.c.name)
    )

    return rows


async def get_contract_overview():
    """Return aggregated contract statistics and detailed rows."""
    contract_base = (
        sqlalchemy.select(
            Contract.c.id.label("id"),
            Contract.c.company_id,
            Contract.c.status,
            sqlalchemy.extract("year", Contract.c.date_valid_to).label("end_year"),
            sqlalchemy.func.coalesce(Contract.c.rent_amount, 0).label("rent_amount"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .select_from(Contract)
        .outerjoin(ContractLandPlot, ContractLandPlot.c.contract_id == Contract.c.id)
        .outerjoin(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .where(Contract.c.status != "terminated")
        .group_by(
            Contract.c.id,
            Contract.c.company_id,
            Contract.c.status,
            Contract.c.date_valid_to,
            Contract.c.rent_amount,
        )
        .subquery()
    )

    total = await database.fetch_one(
        sqlalchemy.select(
            sqlalchemy.func.count(contract_base.c.id).label("contracts"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.area), 0).label("area"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.rent_amount), 0).label("rent"),
            sqlalchemy.func.count(sqlalchemy.distinct(contract_base.c.company_id)).label("companies"),
        )
    )

    payer_count = await database.fetch_val(
        sqlalchemy.select(
            sqlalchemy.func.count(sqlalchemy.distinct(PayerContract.c.payer_id))
        )
        .join(Contract, Contract.c.id == PayerContract.c.contract_id)
        .where(Contract.c.status != "terminated")
    )

    companies = await database.fetch_all(
        sqlalchemy.select(
            Company.c.name.label("name"),
            sqlalchemy.func.count(contract_base.c.id).label("contracts"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.area), 0).label("area"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.rent_amount), 0).label("rent"),
        )
        .join(Company, Company.c.id == contract_base.c.company_id)
        .group_by(Company.c.id)
        .order_by(Company.c.name)
    )

    statuses = await database.fetch_all(
        sqlalchemy.select(
            contract_base.c.status.label("status"),
            sqlalchemy.func.count(contract_base.c.id).label("contracts"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.area), 0).label("area"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.rent_amount), 0).label("rent"),
        )
        .select_from(contract_base)
        .group_by(contract_base.c.status)
        .order_by(contract_base.c.status)
    )

    years = await database.fetch_all(
        sqlalchemy.select(
            contract_base.c.end_year.label("year"),
            sqlalchemy.func.count(contract_base.c.id).label("contracts"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.area), 0).label("area"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.rent_amount), 0).label("rent"),
        )
        .select_from(contract_base)
        .group_by(contract_base.c.end_year)
        .order_by(contract_base.c.end_year)
    )

    rows = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.number.label("number"),
            Company.c.name.label("company_name"),
            sqlalchemy.func.string_agg(
                sqlalchemy.distinct(Payer.c.name), ", "
            ).label("payer_name"),
            Contract.c.status,
            contract_base.c.area,
            sqlalchemy.extract("year", Contract.c.date_valid_from).label("year_from"),
            contract_base.c.end_year.label("year_to"),
            contract_base.c.rent_amount.label("rent_amount"),
        )
        .join(contract_base, contract_base.c.id == Contract.c.id)
        .join(Company, Company.c.id == Contract.c.company_id)
        .outerjoin(PayerContract, PayerContract.c.contract_id == Contract.c.id)
        .outerjoin(Payer, Payer.c.id == PayerContract.c.payer_id)
        .group_by(
            Contract.c.id,
            Contract.c.number,
            Contract.c.status,
            Contract.c.date_valid_from,
            Company.c.name,
            contract_base.c.area,
            contract_base.c.end_year,
            contract_base.c.rent_amount,
        )
        .order_by(Contract.c.number)
    )

    summary = {
        "contracts": total["contracts"] or 0,
        "payers": payer_count or 0,
        "area": float(total["area"] or 0),
        "rent": float(total["rent"] or 0),
        "companies": total["companies"] or 0,
    }

    return summary, companies, statuses, years, rows

# === Звіт по ТОВ ===
async def get_company_report(year: int):
    """Return aggregated info per company for a specific year."""
    payments_sub = (
        sqlalchemy.select(
            Payment.c.agreement_id.label("cid"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.c.amount), 0).label("paid"),
        )
        .where(sqlalchemy.extract("year", Payment.c.payment_date) == year)
        .group_by(Payment.c.agreement_id)
        .subquery()
    )

    contract_active = sqlalchemy.and_(
        Contract.c.date_valid_from <= datetime.utcnow(),
        sqlalchemy.extract("year", Contract.c.date_valid_from) <= year,
        sqlalchemy.or_(
            Contract.c.date_valid_to.is_(None),
            sqlalchemy.extract("year", Contract.c.date_valid_to) >= year,
        ),
    )

    contract_base = (
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.company_id,
            Contract.c.rent_amount,
            sqlalchemy.func.coalesce(payments_sub.c.paid, 0).label("paid"),
        )
        .select_from(Contract)
        .outerjoin(payments_sub, payments_sub.c.cid == Contract.c.id)
        .where(contract_active)
        .subquery()
    )

    info_sub = (
        sqlalchemy.select(
            contract_base.c.company_id,
            sqlalchemy.func.count(contract_base.c.id).label("contracts"),
            sqlalchemy.func.count(sqlalchemy.distinct(ContractLandPlot.c.land_plot_id)).label("plots"),
            sqlalchemy.func.count(sqlalchemy.distinct(PayerContract.c.payer_id)).label("payers"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("contract_area"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.rent_amount), 0).label("rent_total"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(contract_base.c.paid), 0).label("paid_total"),
        )
        .select_from(contract_base)
        .outerjoin(ContractLandPlot, ContractLandPlot.c.contract_id == contract_base.c.id)
        .outerjoin(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .outerjoin(PayerContract, PayerContract.c.contract_id == contract_base.c.id)
        .group_by(contract_base.c.company_id)
        .subquery()
    )

    fields_base = (
        sqlalchemy.select(
            Contract.c.company_id.label("company_id"),
            Field.c.id.label("field_id"),
            Field.c.area_actual.label("area_actual"),
        )
        .select_from(Contract)
        .join(ContractLandPlot, ContractLandPlot.c.contract_id == Contract.c.id)
        .join(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .join(Field, Field.c.id == LandPlot.c.field_id)
        .where(contract_active)
        .group_by(Contract.c.company_id, Field.c.id, Field.c.area_actual)
        .subquery()
    )

    physical_sub = (
        sqlalchemy.select(
            fields_base.c.company_id,
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(fields_base.c.area_actual), 0).label("physical_area"),
        )
        .select_from(fields_base)
        .group_by(fields_base.c.company_id)
        .subquery()
    )

    query = (
        sqlalchemy.select(
            Company.c.name,
            info_sub.c.contracts,
            info_sub.c.plots,
            sqlalchemy.func.coalesce(physical_sub.c.physical_area, 0).label("physical_area"),
            info_sub.c.contract_area,
            info_sub.c.payers,
            info_sub.c.rent_total,
            info_sub.c.paid_total,
        )
        .select_from(info_sub)
        .join(Company, Company.c.id == info_sub.c.company_id)
        .outerjoin(physical_sub, physical_sub.c.company_id == info_sub.c.company_id)
        .order_by(Company.c.name)
    )
    rows = await database.fetch_all(query)
    return rows


async def get_company_contract_types(year: int):
    """Return contract type stats per company for a given year."""
    contract_active = sqlalchemy.and_(
        sqlalchemy.extract("year", Contract.c.date_valid_from) <= year,
        sqlalchemy.or_(
            Contract.c.date_valid_to.is_(None),
            sqlalchemy.extract("year", Contract.c.date_valid_to) >= year,
        ),
    )

    query = (
        sqlalchemy.select(
            Company.c.name.label("company_name"),
            AgreementTemplate.c.type.label("contract_type"),
            sqlalchemy.func.count(sqlalchemy.distinct(Contract.c.id)).label("count"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .select_from(Contract)
        .join(Company, Company.c.id == Contract.c.company_id)
        .join(AgreementTemplate, AgreementTemplate.c.id == Contract.c.template_id)
        .outerjoin(ContractLandPlot, ContractLandPlot.c.contract_id == Contract.c.id)
        .outerjoin(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id)
        .where(contract_active)
        .group_by(Company.c.id, AgreementTemplate.c.type)
        .order_by(Company.c.name, AgreementTemplate.c.type)
    )
    rows = await database.fetch_all(query)
    return rows


async def get_company_sublease():
    """Return sublease stats per company."""
    received = (
        sqlalchemy.select(
            Sublease.c.to_company_id.label("company_id"),
            sqlalchemy.func.count(Sublease.c.id).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .join(LandPlot, LandPlot.c.id == Sublease.c.land_plot_id)
        .group_by(Sublease.c.to_company_id)
        .subquery()
    )

    transferred = (
        sqlalchemy.select(
            Sublease.c.from_company_id.label("company_id"),
            sqlalchemy.func.count(Sublease.c.id).label("plots"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(LandPlot.c.area), 0).label("area"),
        )
        .join(LandPlot, LandPlot.c.id == Sublease.c.land_plot_id)
        .group_by(Sublease.c.from_company_id)
        .subquery()
    )

    query = (
        sqlalchemy.select(
            Company.c.name.label("company_name"),
            sqlalchemy.func.coalesce(received.c.plots, 0).label("received_plots"),
            sqlalchemy.func.coalesce(received.c.area, 0).label("received_area"),
            sqlalchemy.func.coalesce(transferred.c.plots, 0).label("transferred_plots"),
            sqlalchemy.func.coalesce(transferred.c.area, 0).label("transferred_area"),
        )
        .select_from(Company)
        .outerjoin(received, received.c.company_id == Company.c.id)
        .outerjoin(transferred, transferred.c.company_id == Company.c.id)
        .order_by(Company.c.name)
    )
    rows = await database.fetch_all(query)
    return rows


async def get_company_payments_by_year():
    """Return payment accrual and paid amounts per company per year."""
    today = date.today()
    contracts = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.id,
            Contract.c.company_id,
            Contract.c.date_valid_from,
            Contract.c.date_valid_to,
            Contract.c.rent_amount,
        )
        .where(Contract.c.date_valid_from <= datetime.utcnow())
    )
    accruals: dict[tuple[int, int], float] = {}
    for c in contracts:
        if not c["date_valid_from"]:
            continue
        if c["date_valid_from"].date() > today:
            continue
        start_year = c["date_valid_from"].year
        end_year = c["date_valid_to"].year if c["date_valid_to"] else start_year
        for y in range(start_year, end_year + 1):
            key = (c["company_id"], y)
            accruals[key] = accruals.get(key, 0) + float(c["rent_amount"] or 0)

    pay_rows = await database.fetch_all(
        sqlalchemy.select(
            Contract.c.company_id,
            sqlalchemy.extract("year", Payment.c.payment_date).label("year"),
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.c.amount), 0).label("paid"),
        )
        .select_from(Payment)
        .join(Contract, Contract.c.id == Payment.c.agreement_id)
        .where(Contract.c.date_valid_from <= datetime.utcnow())
        .group_by(Contract.c.company_id, sqlalchemy.extract("year", Payment.c.payment_date))
    )
    paid = {(int(r["company_id"]), int(r["year"])): float(r["paid"] or 0) for r in pay_rows}

    rows: list[dict] = []
    keys_seen: set[tuple[int, int]] = set()
    for (cid, year), accrued in accruals.items():
        paid_amount = paid.get((cid, year), 0.0)
        rows.append(
            {
                "company_id": cid,
                "year": year,
                "accrued": accrued,
                "paid": paid_amount,
                "debt": accrued - paid_amount,
            }
        )
        keys_seen.add((cid, year))
    for (cid, year), paid_amount in paid.items():
        if (cid, year) not in keys_seen:
            rows.append(
                {
                    "company_id": cid,
                    "year": year,
                    "accrued": 0.0,
                    "paid": paid_amount,
                    "debt": -paid_amount,
                }
            )

    companies = await database.fetch_all(
        sqlalchemy.select(Company.c.id, Company.c.name)
    )
    names = {c["id"]: c["name"] for c in companies}
    for r in rows:
        r["company"] = names.get(r["company_id"])

    rows.sort(key=lambda x: (x["company"], x["year"]))
    return rows

# === Звіт по ділянках ===
async def get_land_report_rows(
    payer_query: str | None = None,
    company_query: str | None = None,
    contract_query: str | None = None,
    cadaster: str | None = None,
    field_query: str | None = None,
    area_from: float | None = None,
    area_to: float | None = None,
    ngo_from: float | None = None,
    ngo_to: float | None = None,
    end_date: date | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    owners_sub = (
        sqlalchemy.select(
            LandPlotOwner.c.land_plot_id.label("lp_id"),
            sqlalchemy.func.string_agg(Payer.c.name, ", ").label("owners"),
        )
        .join(Payer, Payer.c.id == LandPlotOwner.c.payer_id)
        .group_by(LandPlotOwner.c.land_plot_id)
        .subquery()
    )

    query = (
        sqlalchemy.select(
            LandPlot.c.cadaster,
            LandPlot.c.area,
            LandPlot.c.ngo,
            owners_sub.c.owners.label("payer_name"),
            Contract.c.number.label("contract_number"),
            Company.c.name.label("company_name"),
            Contract.c.date_valid_to,
            Field.c.name.label("field_name"),
            Contract.c.rent_amount,
        )
        .select_from(LandPlot)
        .outerjoin(owners_sub, owners_sub.c.lp_id == LandPlot.c.id)
        .outerjoin(ContractLandPlot, ContractLandPlot.c.land_plot_id == LandPlot.c.id)
        .outerjoin(Contract, Contract.c.id == ContractLandPlot.c.contract_id)
        .outerjoin(Company, Company.c.id == Contract.c.company_id)
        .outerjoin(Field, Field.c.id == LandPlot.c.field_id)
    )

    filters = []
    if payer_query:
        filters.append(owners_sub.c.owners.ilike(f"%{payer_query}%"))
    if company_query:
        filters.append(
            (Company.c.name.ilike(f"%{company_query}%"))
            | (Company.c.short_name.ilike(f"%{company_query}%"))
        )
    if contract_query:
        filters.append(Contract.c.number.ilike(f"%{contract_query}%"))
    if cadaster:
        filters.append(LandPlot.c.cadaster.ilike(f"%{cadaster}%"))
    if field_query:
        filters.append(Field.c.name.ilike(f"%{field_query}%"))
    if area_from is not None:
        filters.append(LandPlot.c.area >= area_from)
    if area_to is not None:
        filters.append(LandPlot.c.area <= area_to)
    if ngo_from is not None:
        filters.append(LandPlot.c.ngo >= ngo_from)
    if ngo_to is not None:
        filters.append(LandPlot.c.ngo <= ngo_to)
    if end_date is not None:
        filters.append(Contract.c.date_valid_to <= end_date)
    if filters:
        query = query.where(sqlalchemy.and_(*filters))

    query = query.order_by(LandPlot.c.cadaster)
    if limit is not None:
        query = query.limit(limit).offset(offset)
    rows = await database.fetch_all(query)
    return rows

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
    sqlalchemy.Column("template_type", sqlalchemy.String(32), default="single"),
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
    sqlalchemy.Column("status", sqlalchemy.String, default="paid"),
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

# === Payroll / Облік ЗП ===
EmployeeRole = sqlalchemy.Table(
    "employee_roles",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("code", sqlalchemy.String(64), unique=True, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.String(255), nullable=False),
)

Employee = sqlalchemy.Table(
    "employees",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("full_name", sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column("telegram_user_id", sqlalchemy.BigInteger, unique=True),
    sqlalchemy.Column("role_code", sqlalchemy.String(64), sqlalchemy.ForeignKey("employee_roles.code"), nullable=False),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("booking_enabled", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("notes", sqlalchemy.Text),
)

PayrollPeriod = sqlalchemy.Table(
    "payroll_periods",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("year", sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("month", sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("status", sqlalchemy.String(32), default="open"),
    sqlalchemy.UniqueConstraint("year", "month", name="uq_payroll_period"),
)

OperationsCatalog = sqlalchemy.Table(
    "operations_catalog",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("role_code", sqlalchemy.String(64), sqlalchemy.ForeignKey("employee_roles.code"), nullable=False),
    sqlalchemy.Column("name", sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column("operation_type", sqlalchemy.String(64), nullable=False),
    sqlalchemy.Column("rate_value", sqlalchemy.Numeric(12, 2), nullable=False),
    sqlalchemy.Column("unit_type", sqlalchemy.String(32), nullable=False),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True),
)

KefRule = sqlalchemy.Table(
    "kef_rules",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("min_hours", sqlalchemy.Numeric(6, 2), nullable=False),
    sqlalchemy.Column("max_hours", sqlalchemy.Numeric(6, 2), nullable=False),
    sqlalchemy.Column("kef_value", sqlalchemy.Numeric(6, 2), nullable=False),
    sqlalchemy.Column("role_code", sqlalchemy.String(64), nullable=True),
)

BookingSettings = sqlalchemy.Table(
    "booking_settings",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("booking_month_cost", sqlalchemy.Numeric(12, 2), nullable=False, default=21000),
    sqlalchemy.Column("kef_money_value", sqlalchemy.Numeric(12, 2), nullable=False, default=1000),
    sqlalchemy.Column("booking_required_kef", sqlalchemy.Numeric(6, 2), nullable=False, default=21),
)

WorkLog = sqlalchemy.Table(
    "work_log",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("employees.id"), nullable=False),
    sqlalchemy.Column("period_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payroll_periods.id"), nullable=False),
    sqlalchemy.Column("date", sqlalchemy.Date, nullable=False),
    sqlalchemy.Column("work_type", sqlalchemy.String(64), nullable=False),
    sqlalchemy.Column("operation_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("operations_catalog.id"), nullable=True),
    sqlalchemy.Column("hours_worked", sqlalchemy.Numeric(6, 2)),
    sqlalchemy.Column("hectares", sqlalchemy.Numeric(10, 2)),
    sqlalchemy.Column("machine_hours", sqlalchemy.Numeric(10, 2)),
    sqlalchemy.Column("units_count", sqlalchemy.Numeric(10, 2)),
    sqlalchemy.Column("payers_count", sqlalchemy.Integer),
    sqlalchemy.Column("late_minutes", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("late_compensated", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("manual_amount", sqlalchemy.Numeric(12, 2)),
    sqlalchemy.Column("include_in_kef_mode", sqlalchemy.String(32), default="time"),
    sqlalchemy.Column("comment", sqlalchemy.Text),
    sqlalchemy.Column("source_type", sqlalchemy.String(32), default="manual"),
    sqlalchemy.Column("source_id", sqlalchemy.Integer, nullable=True),
    sqlalchemy.Column("created_by", sqlalchemy.BigInteger, nullable=True),
    sqlalchemy.Column("kef_amount", sqlalchemy.Numeric(8, 2), default=0),
    sqlalchemy.Column("salary_amount", sqlalchemy.Numeric(12, 2), default=0),
)

EmployeeMonthSummary = sqlalchemy.Table(
    "employee_month_summary",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("employees.id"), nullable=False),
    sqlalchemy.Column("period_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payroll_periods.id"), nullable=False),
    sqlalchemy.Column("total_kef", sqlalchemy.Numeric(10, 2), default=0),
    sqlalchemy.Column("kef_from_prev_month", sqlalchemy.Numeric(10, 2), default=0),
    sqlalchemy.Column("kef_used_for_booking", sqlalchemy.Numeric(10, 2), default=0),
    sqlalchemy.Column("kef_over", sqlalchemy.Numeric(10, 2), default=0),
    sqlalchemy.Column("kef_shortage", sqlalchemy.Numeric(10, 2), default=0),
    sqlalchemy.Column("kef_over_decision", sqlalchemy.String(32), default="no_decision"),
    sqlalchemy.Column("kef_over_paid_amount", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.Column("kef_to_next_month", sqlalchemy.Numeric(10, 2), default=0),
    sqlalchemy.Column("booking_covered_amount", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.Column("booking_uncovered_amount", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.Column("salary_amount", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.Column("bonus_amount", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.Column("fine_amount", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.Column("total_to_pay", sqlalchemy.Numeric(12, 2), default=0),
    sqlalchemy.UniqueConstraint("employee_id", "period_id", name="uq_employee_month_summary"),
)

KefCarryoverHistory = sqlalchemy.Table(
    "kef_carryover_history",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("employees.id"), nullable=False),
    sqlalchemy.Column("from_period_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payroll_periods.id"), nullable=False),
    sqlalchemy.Column("to_period_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("payroll_periods.id"), nullable=False),
    sqlalchemy.Column("kef_amount", sqlalchemy.Numeric(10, 2), nullable=False),
    sqlalchemy.Column("decision_type", sqlalchemy.String(32), nullable=False),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

AttendanceLog = sqlalchemy.Table(
    "attendance_log",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("employees.id"), nullable=False),
    sqlalchemy.Column("date", sqlalchemy.Date, nullable=False),
    sqlalchemy.Column("arrived_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("arrived_latitude", sqlalchemy.Numeric(10, 7), nullable=True),
    sqlalchemy.Column("arrived_longitude", sqlalchemy.Numeric(10, 7), nullable=True),
    sqlalchemy.Column("finished_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("finished_latitude", sqlalchemy.Numeric(10, 7), nullable=True),
    sqlalchemy.Column("finished_longitude", sqlalchemy.Numeric(10, 7), nullable=True),
    sqlalchemy.UniqueConstraint("employee_id", "date", name="uq_employee_attendance_date"),
)

EmployeeTask = sqlalchemy.Table(
    "employee_tasks",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("employees.id"), nullable=False),
    sqlalchemy.Column("title", sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column("description", sqlalchemy.Text),
    sqlalchemy.Column("due_date", sqlalchemy.Date),
    sqlalchemy.Column("status", sqlalchemy.String(32), default="new"),
    sqlalchemy.Column("created_by", sqlalchemy.BigInteger, nullable=True),
)


DEFAULT_EMPLOYEE_ROLES = [
    {"code": "tractor_driver", "name": "Тракторист / комбайнер"},
    {"code": "operations_worker", "name": "Помічник / робота з пайовиками / операційний працівник"},
]

DEFAULT_KEF_RULES = [
    {"min_hours": 0, "max_hours": 6, "kef_value": 0.5, "role_code": None},
    {"min_hours": 6, "max_hours": 12, "kef_value": 1, "role_code": None},
    {"min_hours": 12, "max_hours": 18, "kef_value": 1.5, "role_code": None},
    {"min_hours": 18, "max_hours": 24, "kef_value": 2, "role_code": None},
]

DEFAULT_OPERATIONS = [
    ("tractor_driver", "Оранка 5 корпусів", "field_piecework", 250, "hectare"),
    ("tractor_driver", "Дискова Amazone Catros", "field_piecework", 150, "hectare"),
    ("tractor_driver", "Дискова мала 3 м", "field_piecework", 250, "hectare"),
    ("tractor_driver", "Культиватор Lemken Kompaktor 4 м", "field_piecework", 200, "hectare"),
    ("tractor_driver", "Сівалка Kinze / пропашна 8 рядків", "field_piecework", 200, "hectare"),
    ("tractor_driver", "Сівалка зернова Pottinger", "field_piecework", 200, "hectare"),
    ("tractor_driver", "Обприскувач", "field_piecework", 45, "hectare"),
    ("tractor_driver", "Розкидання добрив", "field_piecework", 50, "hectare"),
    ("tractor_driver", "Обмолот на комбайні", "field_piecework", 200, "hectare"),
    ("tractor_driver", "Перегрузчик зерна", "field_piecework", 250, "hour"),
    ("operations_worker", "Набір нової землі", "contract_area_years", 200, "hectare_year"),
    ("operations_worker", "Пролонгація договорів", "contract_count", 200, "count"),
    ("operations_worker", "Видача орендної плати", "payers_count", 0, "payer"),
]


async def ensure_payroll_defaults():
    for role in DEFAULT_EMPLOYEE_ROLES:
        exists = await database.fetch_one(EmployeeRole.select().where(EmployeeRole.c.code == role["code"]))
        if not exists:
            await database.execute(EmployeeRole.insert().values(**role))

    booking = await database.fetch_one(BookingSettings.select().limit(1))
    if not booking:
        await database.execute(
            BookingSettings.insert().values(
                booking_month_cost=21000,
                kef_money_value=1000,
                booking_required_kef=21,
            )
        )

    existing_rules = await database.fetch_all(KefRule.select())
    if not existing_rules:
        for rule in DEFAULT_KEF_RULES:
            await database.execute(KefRule.insert().values(**rule))

    for role_code, name, op_type, rate_value, unit_type in DEFAULT_OPERATIONS:
        query = OperationsCatalog.select().where(
            (OperationsCatalog.c.role_code == role_code)
            & (OperationsCatalog.c.name == name)
            & (OperationsCatalog.c.operation_type == op_type)
        )
        if not await database.fetch_one(query):
            await database.execute(
                OperationsCatalog.insert().values(
                    role_code=role_code,
                    name=name,
                    operation_type=op_type,
                    rate_value=rate_value,
                    unit_type=unit_type,
                    is_active=True,
                )
            )


async def get_or_create_payroll_period(year: int, month: int):
    query = PayrollPeriod.select().where((PayrollPeriod.c.year == year) & (PayrollPeriod.c.month == month))
    period = await database.fetch_one(query)
    if period:
        return period
    period_id = await database.execute(PayrollPeriod.insert().values(year=year, month=month, status="open"))
    return await database.fetch_one(PayrollPeriod.select().where(PayrollPeriod.c.id == period_id))


async def add_employee(data: dict):
    query = Employee.insert().values(**data)
    return await database.execute(query)


async def get_employee_by_tg_id(tg_id: int):
    return await database.fetch_one(Employee.select().where(Employee.c.telegram_user_id == tg_id))


async def get_employee(employee_id: int):
    return await database.fetch_one(Employee.select().where(Employee.c.id == employee_id))


async def get_employees(active_only: bool | None = None):
    query = Employee.select().order_by(Employee.c.full_name)
    if active_only is not None:
        query = query.where(Employee.c.is_active == active_only)
    return await database.fetch_all(query)


async def add_work_log_entry(data: dict):
    query = WorkLog.insert().values(**data)
    return await database.execute(query)


async def update_work_log_entry(entry_id: int, data: dict):
    query = WorkLog.update().where(WorkLog.c.id == entry_id).values(**data)
    await database.execute(query)


async def get_work_log_entries(period_id: int | None = None, employee_id: int | None = None):
    query = WorkLog.select().order_by(WorkLog.c.date.desc(), WorkLog.c.id.desc())
    if period_id:
        query = query.where(WorkLog.c.period_id == period_id)
    if employee_id:
        query = query.where(WorkLog.c.employee_id == employee_id)
    return await database.fetch_all(query)


async def add_employee_task(data: dict):
    return await database.execute(EmployeeTask.insert().values(**data))


async def get_employee_tasks(employee_id: int, active_only: bool = False):
    query = EmployeeTask.select().where(EmployeeTask.c.employee_id == employee_id).order_by(EmployeeTask.c.due_date.asc())
    if active_only:
        query = query.where(EmployeeTask.c.status.in_(["new", "in_progress"]))
    return await database.fetch_all(query)


async def upsert_attendance_arrival(employee_id: int, work_date: date, lat: float, lon: float):
    existing = await database.fetch_one(
        AttendanceLog.select().where(
            (AttendanceLog.c.employee_id == employee_id) & (AttendanceLog.c.date == work_date)
        )
    )
    now = datetime.utcnow()
    if existing:
        await database.execute(
            AttendanceLog.update().where(AttendanceLog.c.id == existing["id"]).values(
                arrived_at=now,
                arrived_latitude=lat,
                arrived_longitude=lon,
            )
        )
        return existing["id"]
    return await database.execute(
        AttendanceLog.insert().values(
            employee_id=employee_id,
            date=work_date,
            arrived_at=now,
            arrived_latitude=lat,
            arrived_longitude=lon,
        )
    )


async def upsert_attendance_finish(employee_id: int, work_date: date, lat: float, lon: float):
    existing = await database.fetch_one(
        AttendanceLog.select().where(
            (AttendanceLog.c.employee_id == employee_id) & (AttendanceLog.c.date == work_date)
        )
    )
    now = datetime.utcnow()
    if existing:
        await database.execute(
            AttendanceLog.update().where(AttendanceLog.c.id == existing["id"]).values(
                finished_at=now,
                finished_latitude=lat,
                finished_longitude=lon,
            )
        )
        return existing["id"]
    return await database.execute(
        AttendanceLog.insert().values(
            employee_id=employee_id,
            date=work_date,
            finished_at=now,
            finished_latitude=lat,
            finished_longitude=lon,
        )
    )


async def get_attendance_by_employee(employee_id: int, limit: int = 31):
    query = (
        AttendanceLog.select()
        .where(AttendanceLog.c.employee_id == employee_id)
        .order_by(AttendanceLog.c.date.desc())
        .limit(limit)
    )
    return await database.fetch_all(query)


async def get_contract_source_rows(year: int, month: int):
    query = (
        sqlalchemy.select(
            Contract.c.id.label("source_id"),
            Contract.c.date_signed.label("event_date"),
            Contract.c.payer_id,
            Contract.c.duration_years,
            Contract.c.status,
            Contract.c.registration_date,
            sqlalchemy.func.coalesce(
                sqlalchemy.select(sqlalchemy.func.sum(LandPlot.c.area))
                .select_from(ContractLandPlot.join(LandPlot, LandPlot.c.id == ContractLandPlot.c.land_plot_id))
                .where(ContractLandPlot.c.contract_id == Contract.c.id)
                .scalar_subquery(),
                0,
            ).label("area"),
        )
        .where(sqlalchemy.extract("year", Contract.c.date_signed) == year)
        .where(sqlalchemy.extract("month", Contract.c.date_signed) == month)
        .order_by(Contract.c.date_signed.desc())
    )
    return await database.fetch_all(query)


async def get_lease_payment_source_rows(year: int, month: int):
    query = (
        sqlalchemy.select(
            Payment.c.id.label("source_id"),
            Payment.c.payment_date.label("event_date"),
            Payment.c.amount,
            Payment.c.agreement_id,
            Contract.c.payer_id,
        )
        .select_from(Payment.join(Contract, Contract.c.id == Payment.c.agreement_id))
        .where(sqlalchemy.extract("year", Payment.c.payment_date) == year)
        .where(sqlalchemy.extract("month", Payment.c.payment_date) == month)
        .order_by(Payment.c.payment_date.desc())
    )
    return await database.fetch_all(query)

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

async def get_agreement_templates(active_only: bool | None = None, template_type: str | None = None):
    query = AgreementTemplate.select()
    if active_only is not None:
        query = query.where(AgreementTemplate.c.is_active == active_only)
    if template_type:
        query = query.where(AgreementTemplate.c.template_type == template_type)
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
        "ALTER TABLE \"agreement_template\" ADD COLUMN IF NOT EXISTS template_type VARCHAR(32) DEFAULT 'single'"
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
    conn.execute(sqlalchemy.text(
        'ALTER TABLE "payment" ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT \'paid\''
    ))
