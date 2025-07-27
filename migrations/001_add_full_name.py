import os
import asyncio
from databases import Database

DATABASE_URL = os.getenv("DATABASE_URL")

async def main():
    db = Database(DATABASE_URL)
    await db.connect()
    await db.execute(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);'
    )
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
