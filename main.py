import asyncio
import os

from dotenv import load_dotenv
from crawler import setup_threads
from database.database_manager import DatabaseManager
from logger.logger import logger


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
    logger.info('Application started.')

    # Load env variables.
    postgres_user, postgres_password, postgres_db = load_env()

    # Setup database manager.
    database_manager = DatabaseManager(url=f"postgresql+asyncpg://"
                                           f"{postgres_user}:"
                                           f"{postgres_password}@localhost:5432/"
                                           f"{postgres_db}")

    # Run the spider.

    # *****
    # TODO: The frontier strategy needs to follow the breadth-first strategy. In the report explain how is your strategy implemented.
    # *****

    # TODO: incorporate seed URLs
    # TODO: implement multi-threading with database locking
    # start crawling from each seed URL
    # for seed_url in seed_urls:
    #    crawl(seed_url)

    # Test with robots.txt and large sitemap. 
    # !!! It takes 1 HOUR to build whole URL tree !!!
    # await start_crawler(start_url='https://www.gov.si')

    # Test with redirect and no robots.txt, but with hidden sitemap.xml
    # It takes 2 minutes to build whole URL tree
    # await start_crawler(start_url='https://evem.gov.si')

    # Test with robots.txt and sitemap url, but sitemap is 404 not found page
    # await start_crawler(start_url='https://e-uprava.gov.si')

    # Test with robots.txt and small sitemap. 
    # It takes 20 seconds to build the URL tree
    # !!! The sitemap has irregular sitemap URLs !!! 
    # await start_crawler(start_url='https://e-prostor.gov.si')

    await setup_threads(database_manager=database_manager)

    # Clean database manager.
    await database_manager.cleanup()

    logger.info('Application finished.')


if __name__ == '__main__':
    asyncio.run(main())
