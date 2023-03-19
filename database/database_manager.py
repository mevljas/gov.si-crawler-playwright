from sqlalchemy import select, Row, ScalarResult, Result, Sequence, update, exc
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.sql.functions import count, func

from database.models import meta, Page
from logger.logger import logger


class DatabaseManager:
    def __init__(self):
        self._engine: AsyncEngine = None

    def create_database_engine(self, user: str, password: str, db: str):
        """
        Creates a Sqlalchemy database engine.
        """
        logger.debug('Creating database engine.')
        self._engine = create_async_engine(f"postgresql+asyncpg://"
                                           f"{user}:"
                                           f"{password}@localhost:5432/"
                                           f"{db}")
        logger.debug('Creating database engine finished.')

    async def get_session_maker(self) -> async_sessionmaker:
        logger.debug('Getting database session.')
        # return async_sessionmaker(self.engine, expire_on_commit=False)
        return async_sessionmaker(self._engine)

    async def cleanup(self):
        logger.debug('Cleaning database engine.')
        """
        Cleanup database engine.    
        """
        await self._engine.dispose()
        logger.debug('Cleaning database finished.')

    async def create_models(self):
        """
        Creates all required database tables from the declared models.
        """
        logger.debug('Creating ORM modules.')
        async with self._engine.begin() as conn:
            await conn.run_sync(meta.create_all)
        logger.debug('Finished creating ORM modules.')

    async def delete_tables(self):
        """
        Deletes all tables from the database.
        """
        logger.debug('Deleting database tables.')
        async with self._engine.begin() as conn:
            await conn.run_sync(meta.reflect)
            await conn.run_sync(meta.drop_all)
        logger.debug('Finished deleting database tables.')

    async def get_frontier(self) -> list:
        """
        Gets the frontier.
        """
        logger.debug('Getting the frontier.')
        async_session: async_sessionmaker[AsyncSession] = await self.get_session_maker()
        async with async_session() as session:
            async with session.begin():
                result: Result = await session.execute(select(Page).where(Page.page_type_code == "FRONTIER"))
                logger.debug('Got frontier.')
                return [(row.id, row.url) for row in result.scalars()]

    async def get_frontier_links(self) -> set[str]:
        """
        Gets all links from the frontier.
        """
        logger.debug('Getting links from the frontier.')
        async_session: async_sessionmaker[AsyncSession] = await self.get_session_maker()
        async with async_session() as session:
            async with session.begin():
                result: Result = await session.execute(select(Page.url).where(Page.page_type_code == "FRONTIER"))
                logger.debug('Got links from the frontier.')
                return set([url for url in result.scalars()])

    async def get_visited_pages_count(self) -> int:
        """
        Gets all links from the frontier.
        """
        logger.debug('Getting visited pages count.')
        async_session: async_sessionmaker[AsyncSession] = await self.get_session_maker()
        async with async_session() as session:
            async with session.begin():
                result: int = await session.scalar(
                    select(func.count()).select_from(Page).where(Page.page_type_code != "FRONTIER"))
                logger.debug('Got visited pages count.')
                return result

    async def remove_from_frontier(self, id: int):
        """
        Removes a link from frontier.
        """
        logger.debug('Removing a link from the frontier.')
        async_session: async_sessionmaker[AsyncSession] = await self.get_session_maker()
        async with async_session() as session:
            async with session.begin():
                await session.execute(update(Page).where(Page.id == id).values(page_type_code='HTML'))
                await session.commit()
                logger.debug('Link removed from the frontier.')

    async def add_to_frontier(self, links: set[str]):
        """
        Adds new links to the frontier.
        """
        logger.debug('Adding links to the frontier.')
        async_session: async_sessionmaker[AsyncSession] = await self.get_session_maker()
        async with async_session() as session:
            for link in links:
                async with session.begin():
                    try:
                        session.add(Page(url=link, page_type_code='FRONTIER'))
                        await session.commit()
                    except exc.IntegrityError:
                        logger.debug('Adding links failed, some are already in the frontier.')
            logger.debug('Added links to the frontier.')
