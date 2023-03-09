import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from database.database_manager import DatabaseManager
from database.models import meta, DataType, PageType
import logging


def load_env() -> (str, str, str):
    """
    Load ENV variables.
    :return: postgres_user, postgres_password, postgres_db
    """
    load_dotenv()
    postgres_user = os.getenv('POSTGRES_USER')
    postgres_password = os.getenv('POSTGRES_PASSWORD')
    postgres_db = os.getenv('POSTGRES_DB')
    return postgres_user, postgres_password, postgres_db


async def seed_default(async_session_maker: async_sessionmaker[AsyncSession]):
    """
    Inserts required started data to the database.
    """
    logging.debug('Seeding the database started.')
    async with async_session_maker() as session:
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
    logging.debug('Seeding the database finished.')


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Migration started.')

    # Load env variables.
    postgres_user, postgres_password, postgres_db = load_env()

    # Setup database manager.
    database_manager = DatabaseManager()
    database_manager.create_database_engine(user=postgres_user, password=postgres_password, db=postgres_db)

    # Create database tables.
    await database_manager.create_models()

    # Get database session maker
    async_session_maker = await database_manager.get_session_maker()

    await seed_default(async_session_maker)

    # Clean database manager.
    await database_manager.cleanup()
    logging.info('Migration finished.')


if __name__ == '__main__':
    asyncio.run(main())
