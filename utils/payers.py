import sqlalchemy
from db import database, Contract, Payer, PayerContract

async def get_payers_for_contract(contract_id: int) -> list[str]:
    """Return list of payer names associated with a contract.

    First tries to fetch payers from the many-to-many ``payer_contract`` table.
    If no rows are found, falls back to the legacy ``contract.payer_id``
    relationship used in older records.
    """
    rows = await database.fetch_all(
        sqlalchemy.select(Payer.c.name)
        .select_from(Payer)
        .join(PayerContract, PayerContract.c.payer_id == Payer.c.id)
        .where(PayerContract.c.contract_id == contract_id)
    )
    if rows:
        return [r["name"] for r in rows]
    row = await database.fetch_one(
        sqlalchemy.select(Payer.c.name)
        .select_from(Contract)
        .join(Payer, Payer.c.id == Contract.c.payer_id)
        .where(Contract.c.id == contract_id)
    )
    return [row["name"]] if row else []
