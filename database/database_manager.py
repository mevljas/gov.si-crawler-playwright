import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


class DatabaseManager:
    def __init__(self):
        self._engine = None

    def create_database_engine(self, user: str, password: str, db: str):
        """
        Creates a Sqlalchemy database engine.
        """
        logging.debug('Creating database engine.')
        self._engine = create_async_engine(f"postgresql+asyncpg://"
                                                 f"{user}:"
                                                 f"{password}@localhost:5432/"
                                                 f"{db}")
        logging.debug('Creating database engine finished.')

    async def get_session(self) -> async_sessionmaker:
        logging.debug('Getting database session.')
        # return async_sessionmaker(self.engine, expire_on_commit=False)
        return async_sessionmaker(self._engine)

    async def cleanup(self):
        logging.debug('Cleaning database engine.')
        """
        Cleanup database engine.    
        """
        await self._engine.dispose()
        logging.debug('Cleaning database finished.')
