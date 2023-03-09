import asyncio
import logging

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.database_helper import create_database_engine


async def setup():
    """
    Setups all required dependencies.
    """

    logging.info('Starting application setup.')
    load_dotenv()
    engine = create_database_engine()
    # async_sessionmaker: a factory for new AsyncSession objects.
    # expire_on_commit - don't expire objects after transaction commit
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    logging.info('Finished application setup.')
    return engine, async_session


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Application started.')
    engine, async_session = await setup()

    # for AsyncEngine created in function scope, close and
    # clean-up pooled connections

    await engine.dispose()
    logging.info('Application finished.')


if __name__ == '__main__':
    asyncio.run(main())
