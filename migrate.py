import asyncio
import os

import asyncpg
from dotenv import load_dotenv
from sqlalchemy import schema
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from database.database_helper import create_database_engine
from database.models import meta, DataType, PageType


# Create ORM models.
async def create_models(conn):
    print('Creating ORM modules.')
    await conn.run_sync(meta.create_all)
    print('Finished creating ORM modules.')


async def seed_default(async_session: async_sessionmaker[AsyncSession]):
    print('Seeding the database started.')
    async with async_session() as session:
        async with session.begin():
            session.add_all(
                [
                    DataType(code='PDF'),
                    DataType(code='DOC'),
                    DataType(code='DOCX'),
                    DataType(code='PPT'),
                    DataType(code='PPTX'),
                    PageType(code='HTML'),
                    PageType(code='BINARY'),
                    PageType(code='DUPLICATE'),
                    PageType(code='FRONTIER'),
                ]
            )
    print('Seeding the database finished.')


# Project setup.
async def setup():
    print('Starting setup.')
    load_dotenv()
    engine = create_database_engine()
    # await connect_create_if_not_exists()
    # async_sessionmaker: a factory for new AsyncSession objects.
    # expire_on_commit - don't expire objects after transaction commit
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        database = os.getenv('POSTGRES_DB')
        await create_models(conn)
    await seed_default(async_session)
    print('Finished setup.')
    return engine, async_session


async def main():
    print('Migration started.')
    engine, async_session = await setup()
    # for AsyncEngine created in function scope, close and
    # clean-up pooled connections
    await engine.dispose()
    print('Migration finished.')


if __name__ == '__main__':
    asyncio.run(main())
