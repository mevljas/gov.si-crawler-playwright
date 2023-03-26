import threading
from asyncio import current_task
from datetime import datetime

from sqlalchemy import select, Result, update, exc, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncEngine, AsyncSession, \
    async_scoped_session
from sqlalchemy.sql.functions import func

from database.models import PageData, meta, Page, Site, Link, Image
from logger.logger import logger


class DatabaseManager:
    def __init__(self, url: str):
        self.db_connections = threading.local()
        self.url = url

    def async_engine(self) -> AsyncEngine:
        if not hasattr(self.db_connections, "engine"):
            logger.debug('Getting async engine.')
            self.db_connections.engine = create_async_engine(self.url)
            logger.debug('Creating database engine finished.')
        return self.db_connections.engine

    def async_session_factory(self) -> async_sessionmaker:
        logger.debug('Getting async session factory.')
        if not hasattr(self.db_connections, "session_factory"):
            engine = self.async_engine()
            self.db_connections.session_factory = async_sessionmaker(bind=engine)
        return self.db_connections.session_factory

    def async_scoped_session(self) -> async_scoped_session[AsyncSession]:
        logger.debug('Getting async scoped session.')
        if not hasattr(self.db_connections, "scoped_session"):
            session_factory = self.async_session_factory()
            self.db_connections.scoped_session = async_scoped_session(session_factory,
                                                                      scopefunc=current_task)
        return self.db_connections.scoped_session

    async def cleanup(self):
        logger.debug('Cleaning database engine.')
        """
        Cleanup database engine.    
        """
        await self.db_connections.engine.dispose()
        logger.debug('Cleaning database finished.')

    async def create_models(self):
        """
        Creates all required database tables from the declared models.
        """
        logger.debug('Creating ORM modules.')
        async with self.async_engine().begin() as conn:
            await conn.run_sync(meta.create_all)
        logger.debug('Finished creating ORM modules.')

    async def delete_tables(self):
        """
        Deletes all tables from the database.
        """
        logger.debug('Deleting database tables.')
        async with self.async_engine().begin() as conn:
            await conn.run_sync(meta.reflect)
            await conn.run_sync(meta.drop_all)
        logger.debug('Finished deleting database tables.')

    async def pop_frontier(self) -> tuple[int, str]:
        """
        Pops the first page off the frontier.
        """
        logger.debug('Getting the top of the frontier.')
        async with self.async_session_factory()() as session:
            page: Page = (await session.execute(select(Page).where(Page.page_type_code == "FRONTIER").limit(1).with_for_update())).scalars().first()
            logger.debug('Got the top of the frontier.')
            if page is not None:
                page_id, page_url = page.id, page.url
                await session.execute(update(Page).where(Page.id == page.id).values(page_type_code='CRAWLING'))
                await session.commit()
                return page_id, page_url
            logger.debug('Frontier is empty')
            return

    async def get_frontier_links(self) -> set[str]:
        """
        Gets all links from the frontier.
        """
        logger.debug('Getting links from the frontier.')
        async with self.async_session_factory()() as session:
            result: Result = await session.execute(select(Page.url).where(Page.page_type_code == "FRONTIER"))
            logger.debug('Got links from the frontier.')

            return set([url for url in result.scalars()])

    async def get_visited_pages_count(self) -> int:
        """
        Gets all links from the frontier.
        """
        logger.debug('Getting visited pages count.')
        async with self.async_session_factory()() as session:
            result: int = await session.scalar(
                select(func.count()).select_from(Page).where(Page.page_type_code != "FRONTIER"))
            logger.debug('Got visited pages count.')

            return result

    async def remove_from_frontier(self, page_id: int):
        """
        Removes a link from frontier.
        """
        logger.debug('Removing a link from the frontier.')
        async with self.async_session_factory()() as session:
            await session.execute(delete(Page).where(Page.id == page_id))
            await session.commit()

            logger.debug('Link removed from the frontier.')

    async def add_to_frontier(self, links: set[str]):
        """
        Adds new links to the frontier.
        """
        logger.debug('Adding links to the frontier.')
        async with self.async_session_factory()() as session:
            for link in links:
                try:
                    session.add(Page(url=link, page_type_code='FRONTIER'))
                    await session.commit()
                except exc.IntegrityError:
                    await session.rollback()
                    logger.debug('Adding links failed, some are already in the frontier.')

            logger.debug('Added links to the frontier.')

    async def save_page(self, page_id: int, status: int, site_id: int, html: str = None, html_hash: str = None,
                        page_type_code: str = 'HTML'):
        """
        Saved a visited page to the database.
        """
        logger.debug('Saving page to the database.')
        async with self.async_session_factory()() as session:
            await session.execute(
                update(Page).where(Page.id == page_id).values(page_type_code=page_type_code,
                                                              html_content=html,
                                                              http_status_code=status,
                                                              site_id=site_id,
                                                              accessed_time=datetime.now(),
                                                              html_content_hash=html_hash))
            await session.commit()

            logger.debug('Page saved to the database.')

    async def create_empty_page(self, url: str, site_id: int, page_type_code: str='HTML') -> int:
        """
        Creates an empty page with only the url and site_id, which is then filled in later. 
        This is used for on-the-fly page saves, usually they would and should be created when adding to frontier.
        Return the page's id.
        """
        logger.debug('Saving new page to the database.')
        page_id: int
        async with self.async_session_factory()() as session:
            new_page: Page = Page(site_id=site_id, url=url, page_type_code=page_type_code)
            session.add(new_page)
            await session.flush()
            page_id = new_page.id
            await session.commit()

            logger.debug(f'New page saved to the database with an id {page_id}.')
            
            return page_id

    async def save_site(self, domain: str, robots_content: str, sitemap_content) -> int:
        """
        Saved a visited site to the database.
        Return a site's id.
        """
        logger.debug('Saving site to the database.')
        site_id: int
        async with self.async_session_factory()() as session:
            new_site: Site = Site(domain=domain, robots_content=robots_content, sitemap_content=sitemap_content)
            session.add(new_site)
            await session.flush()
            site_id = new_site.id
            await session.commit()

            logger.debug(f'Site saved to the database with an id {site_id}.')

            return site_id

    async def get_site(self, domain: str) -> (int, str, str, str):
        """
        Gets the site from the database.
        """
        logger.debug('Getting the site from the database.')
        async with self.async_session_factory()() as session:
            result: Result = await session.execute(select(Site).where(Site.domain == domain))
            page = result.scalars().first()
            if page is not None:
                logger.debug('Got the site from the database.')

                return page.id, page.domain, page.robots_content, page.sitemap_content
            logger.debug('The site hasnt been found in the database.')

            return None

    async def check_pages_hash_collision(self, html_hash: str) -> (int, int):
        """
        Check the database for duplicate pages and return the original page's id.
        """
        logger.debug('Checking the database for duplicate pages..')
        async with self.async_session_factory()() as session:
            result: Result = await session \
                .execute(select(Page)
                         .with_only_columns(Page.id, Page.site_id)
                         .where(Page.html_content_hash == html_hash))
            page = result.first()
            if page is not None:
                page_id = page.id
                logger.debug(f'Duplicate found with an id {page_id}.')

                return page_id, page.site_id
            logger.debug('Duplicate page hasnt been found.')

            return None

    async def add_page_link(self, original_page_id: int, duplicate_page_id: int):
        """
        Adds a new page duplicate link.
        """
        logger.debug('Adding a new page duplicate link.')
        async with self.async_session_factory()() as session:
            session.add(Link(from_page=duplicate_page_id, to_page=original_page_id))
            await session.commit()

            logger.debug('Duplicate link added successfully.')

    async def save_images(self, images: list[Image]):
        """
        Saves new images to the database.
        """
        logger.debug('Saving images to the database.')
        async with self.async_session_factory()() as session:
            session.add_all(images)
            await session.commit()

            logger.debug('Images saved to the database.')

    async def save_page_data(self, page_data_entries: list[PageData]):
        """
        Saves new page data to the database.
        """
        logger.debug('Saving page data entries to the database.')
        async with self.async_session_factory()() as session:
                session.add_all(page_data_entries)
                await session.commit()

                logger.debug('Page data entries saved to the database.')

    async def mark_page_as_failed(self, page_id: int):
        """
        Marks an attempted page as failed. Pages are marked as failed if there is any exception during page access.
        """
        logger.debug('Marking page as failed in the database.')
        async with self.async_session_factory()() as session:
            await session.execute(update(Page).where(Page.id == page_id).values(page_type_code="FAILED"))
            await session.commit()

            logger.debug('Page marked as failed.')