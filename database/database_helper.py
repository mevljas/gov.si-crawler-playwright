import logging
import os

from sqlalchemy.ext.asyncio import create_async_engine

"""
Creates and returns Sqlalchemy database engine.
"""


def create_database_engine():
    logging.debug('Creating ORM engine.')
    engine = create_async_engine(f"postgresql+asyncpg://"
                                 f"{os.getenv('POSTGRES_USER')}:"
                                 f"{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/"
                                 f"{os.getenv('POSTGRES_DB')}")
    logging.debug('Creating ORM engine finished.')
    return engine
