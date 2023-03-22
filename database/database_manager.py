from asyncio import current_task
from datetime import datetime

from sqlalchemy import select, Row, ScalarResult, Result, Sequence, update, exc, delete, NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncEngine, AsyncSession, \
    async_scoped_session
from sqlalchemy.sql.functions import count, func

from database.models import meta, Page, Site, Link, Image
from logger.logger import logger


class DatabaseManager:
    def __init__(self):
        self._asyncEngine: AsyncEngine = None

    def create_database_engine(self, user: str, password: str, db: str):
        """
        Creates a Sqlalchemy database engine.
        """
        logger.debug('Creating database engine.')
        self._asyncEngine = create_async_engine(f"postgresql+asyncpg://"
                                                f"{user}:"
                                                f"{password}@localhost:5432/"
                                                f"{db}",
                                                poolclass=NullPool)
        # TODO: removing pool class is an ugly workaround.
        logger.debug('Creating database engine finished.')

    def async_session_factory(self) -> async_sessionmaker:
        logger.debug('Getting async session factory.')
        # return async_sessionmaker(self.engine, expire_on_commit=False)
        return async_sessionmaker(bind=self._asyncEngine)

    def get_async_scoped_session(self) -> async_scoped_session[AsyncSession]:
        session_factory = self.async_session_factory()
        return async_scoped_session(session_factory, scopefunc=current_task)

    async def cleanup(self):
        logger.debug('Cleaning database engine.')
        """
        Cleanup database engine.    
        """
        await self._asyncEngine.dispose()
        logger.debug('Cleaning database finished.')

    async def create_models(self):
        """
        Creates all required database tables from the declared models.
        """
        logger.debug('Creating ORM modules.')
        async with self._asyncEngine.begin() as conn:
            await conn.run_sync(meta.create_all)
        logger.debug('Finished creating ORM modules.')

    async def delete_tables(self):
        """
        Deletes all tables from the database.
        """
        logger.debug('Deleting database tables.')
        async with self._asyncEngine.begin() as conn:
            await conn.run_sync(meta.reflect)
            await conn.run_sync(meta.drop_all)
        logger.debug('Finished deleting database tables.')

    async def get_frontier(self) -> list:
        """
        Gets the frontier.
        """
        logger.debug('Getting the frontier.')
        session = self.get_async_scoped_session()
        async with session.begin():
            result: Result = await session.execute(select(Page).where(Page.page_type_code == "FRONTIER"))
            logger.debug('Got frontier.')
            await session.remove()
            return [(row.id, row.url) for row in result.scalars()]

    async def get_frontier_links(self) -> set[str]:
        """
        Gets all links from the frontier.
        """
        logger.debug('Getting links from the frontier.')
        session = self.get_async_scoped_session()
        async with session.begin():
            result: Result = await session.execute(select(Page.url).where(Page.page_type_code == "FRONTIER"))
            logger.debug('Got links from the frontier.')
            await session.remove()
            return set([url for url in result.scalars()])

    async def get_visited_pages_count(self) -> int:
        """
        Gets all links from the frontier.
        """
        logger.debug('Getting visited pages count.')
        session = self.get_async_scoped_session()
        async with session.begin():
            result: int = await session.scalar(
                select(func.count()).select_from(Page).where(Page.page_type_code != "FRONTIER"))
            logger.debug('Got visited pages count.')
            await session.remove()
            return result

    async def mark_page_visited(self, page_id: int, page_type_code: str = 'HTML'):
        """
        Marks a page as visited.
        """
        logger.debug('Marking page as visited.')
        session = self.get_async_scoped_session()
        async with session.begin():
            # TODO: We should probably clear page_type_code instead of setting it to html?
            await session.execute(update(Page).where(Page.id == page_id).values(page_type_code=page_type_code))
            await session.commit()
            await session.remove()
            logger.debug('Page marked as visited.')

    async def remove_from_frontier(self, page_id: int):
        """
        Removes a link from frontier.
        """
        logger.debug('Removing a link from the frontier.')
        session = self.get_async_scoped_session()
        async with session.begin():
            await session.execute(delete(Page).where(Page.id == page_id))
            await session.commit()
            await session.remove()
            logger.debug('Link removed from the frontier.')

    async def add_to_frontier(self, links: set[str]):
        """
        Adds new links to the frontier.
        """
        logger.debug('Adding links to the frontier.')
        session = self.get_async_scoped_session()
        async with session.begin():
            for link in links:
                async with session.begin():
                    try:
                        session.add(Page(url=link, page_type_code='FRONTIER'))
                        await session.commit()
                    except exc.IntegrityError:
                        logger.debug('Adding links failed, some are already in the frontier.')
            await session.remove()
            logger.debug('Added links to the frontier.')

    async def save_page(self, page_id: int, status: str, site_id: int, html: str = None, html_hash: str = None,
                        page_type_code: str = 'HTML'):
        """
        Saved a visited page to the database.
        """
        logger.debug('Saving page to the database.')
        session = self.get_async_scoped_session()
        async with session.begin():
            await session.execute(
                update(Page).where(Page.id == page_id).values(page_type_code=page_type_code,
                                                                  html_content=html,
                                                                  http_status_code=status,
                                                                  site_id=site_id,
                                                                  accessed_time=datetime.now(),
                                                                  html_content_hash=html_hash))
            await session.commit()
        await session.remove()
        logger.debug('Page saved to the database.')

    async def save_site(self, domain: str, robots_content: str, sitemap_content) -> int:
        """
        Saved a visited site to the database.
        Return a site's id.
        """
        logger.debug('Saving site to the database.')
        site_id: int
        session = self.get_async_scoped_session()
        new_site: Site = Site(domain=domain, robots_content=robots_content, sitemap_content=sitemap_content)
        async with session.begin():
            session.add(new_site)
            await session.flush()
            site_id = new_site.id
            await session.commit()
        logger.debug(f'Site saved to the database with an id {site_id}.')
        await session.remove()
        return site_id

    async def get_site(self, domain: str) -> (int, str, str, str):
        """
        Gets the site from the database.
        """
        logger.debug('Getting the site from the database.')
        session = self.get_async_scoped_session()
        async with session.begin():
            result: Result = await session.execute(select(Site).where(Site.domain == domain))
            page = result.scalars().first()
            if page is not None:
                logger.debug('Got the site from the database.')
                await session.remove()
                return page.id, page.domain, page.robots_content, page.sitemap_content
            logger.debug('The site hasnt been found in the database.')
            await session.remove()
            return None

    async def check_pages_hash_collision(self, html_hash: str) -> (int, int):
        """
        Check the database for duplicate pages and return the original page's id.
        """
        logger.debug('Checking the database for duplicate pages..')
        session = self.get_async_scoped_session()
        async with session.begin():
            result: Result = await session \
                    .execute(select(Page)
                             .with_only_columns(Page.id, Page.site_id)
                             .where(Page.html_content_hash == html_hash))
            page = result.first()
            if page is not None:
                page_id = page.id
                logger.debug(f'Duplicate found with an id {page_id}.')
                await session.remove()
                return page_id, page.site_id
            logger.debug('Duplicate page hasnt been found.')
            await session.remove()
            return None

    async def add_page_link(self, original_page_id: int, duplicate_page_id: int):
        """
        Adds a new page duplicate link.
        """
        logger.debug('Adding a new page duplicate link.')
        session = self.get_async_scoped_session()
        async with session.begin():
            session.add(Link(from_page=duplicate_page_id, to_page=original_page_id))
            await session.commit()
        await session.remove()
        logger.debug('Duplicate link added successfully.')

    async def save_images(self, images: list[Image]):
        """
        Saves new images to the database.
        """
        logger.debug('Saving images to the database.')
        session = self.get_async_scoped_session()
        async with session.begin():
            session.add_all(images)
            await session.commit()
            await session.remove()
        logger.debug('Images saved to the database.')
