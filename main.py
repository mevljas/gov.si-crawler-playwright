import asyncio
import logging
import os

from dotenv import load_dotenv

from crawler import crawl
from database.database_manager import DatabaseManager


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


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Application started.')

    # Load env variables.
    postgres_user, postgres_password, postgres_db = load_env()

    # Setup database manager.
    database_manager = DatabaseManager()
    database_manager.create_database_engine(user=postgres_user, password=postgres_password, db=postgres_db)

    # Run the spider.
    await crawl('https://www.gov.si')

    # Clean database manager.
    await database_manager.cleanup()

    logging.info('Application finished.')


if __name__ == '__main__':
    asyncio.run(main())
