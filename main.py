import asyncio
import os

from dotenv import load_dotenv
from crawler import setup_threads
from database.database_manager import DatabaseManager
from logger.logger import logger


def load_env() -> (str, str, str, int):
    """
    Load ENV variables.
    :return: postgres_user, postgres_password, postgres_db
    """
    load_dotenv()
    postgres_user = os.getenv('POSTGRES_USER')
    postgres_password = os.getenv('POSTGRES_PASSWORD')
    postgres_db = os.getenv('POSTGRES_DB')
    n_threads = int(os.getenv('N_THREADS'))
    return postgres_user, postgres_password, postgres_db, n_threads


async def main():
    logger.info('Application started.')

    # Load env variables.
    postgres_user, postgres_password, postgres_db, n_threads = load_env()

    # Setup database manager.
    database_manager = DatabaseManager(url=f"postgresql+asyncpg://"
                                           f"{postgres_user}:"
                                           f"{postgres_password}@localhost:5432/"
                                           f"{postgres_db}")

    # Run the spider.
    await setup_threads(database_manager=database_manager, n_threads=n_threads)

    logger.info('Application finished.')


if __name__ == '__main__':
    asyncio.run(main())
