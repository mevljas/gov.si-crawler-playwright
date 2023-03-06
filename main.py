import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from helpers.models import meta, DataType, PageType


# Connect to the database.
def create_database_engine():
    print('Creating ORM engine.')
    engine = create_async_engine(f"postgresql+asyncpg://"
                                 f"{os.getenv('POSTGRES_USER')}:"
                                 f"{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/"
                                 f"{os.getenv('POSTGRES_DB')}")
    print('Creating ORM engine finished.')
    return engine


# Create ORM models.
async def create_models(conn):
    print('Creating ORM modules.')
    await conn.run_sync(meta.create_all)
    print('Finished creating ORM modules.')


async def seed_default(async_session: async_sessionmaker[AsyncSession]):
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
        # await session.commit()


# Project setup.
async def setup():
    print('Starting application setup.')
    load_dotenv()
    engine = create_database_engine()
    # async_sessionmaker: a factory for new AsyncSession objects.
    # expire_on_commit - don't expire objects after transaction commit
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await create_models(conn)
    await seed_default(async_session)
    print('Finished application setup.')
    return engine, async_session


async def main():
    print('Application started.')
    engine, async_session = await setup()
    # for AsyncEngine created in function scope, close and
    # clean-up pooled connections
    await engine.dispose()
    print('Application finished.')


if __name__ == '__main__':
    asyncio.run(main())
