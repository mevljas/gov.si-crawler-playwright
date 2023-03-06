import os

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine


# Connect to the database.
def create_database_engine():
    print('Creating ORM engine.')
    engine = create_async_engine(f"postgresql+asyncpg://"
                                 f"{os.getenv('POSTGRES_USER')}:"
                                 f"{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/"
                                 f"{os.getenv('POSTGRES_DB')}")
    print('Creating ORM engine finished.')
    return engine


