import asyncio

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from database.database_helper import create_database_engine
from database.models import meta, DataType, PageType


# Project setup.
async def setup():
    print('Starting application setup.')
    load_dotenv()
    engine = create_database_engine()
    # async_sessionmaker: a factory for new AsyncSession objects.
    # expire_on_commit - don't expire objects after transaction commit
    async_session = async_sessionmaker(engine, expire_on_commit=False)
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
