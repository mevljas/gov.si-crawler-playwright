import asyncio
import hashlib
import urllib.robotparser
from threading import Thread
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from crawler_helper.constants import USER_AGENT, default_domain_delay
from crawler_helper.crawler_helper import CrawlerHelper
from database.database_manager import DatabaseManager
from database.models import PageData
from logger.logger import logger

# TODO: implement locking for available times
domain_available_times = {}  # A set with domains next available times.
ip_available_times = {}  # A set with ip next available times.
threads_status = {}  # Remember for each thread whether is sleeping (False) or running (True).


async def crawl_url(current_url: str, browser_page: Page, robot_file_parser: RobotFileParser,
                    database_manager: DatabaseManager, page_id: int):
    """
    Crawls the provided current_url.
    :param current_url: Url to be crawled
    :param browser_page: Browser page
    :param robot_file_parser: parser for robots.txt
    :return:
    """
    logger.info(f'Crawling url {current_url} started.')

    # Fix shortened URLs (if necessary).
    current_url = CrawlerHelper.fix_shortened_url(url=current_url)

    # Fetch page
    try:
        (url, html, data_type, status) = await CrawlerHelper.get_page(url=current_url, page=browser_page)
    except Exception as e:
        # Mark page as failed and goto next page
        await database_manager.mark_page_as_failed(page_id=page_id)
        logger.warning(f'Opening page {current_url} failed with an error {e}.')
        return
    
    if html:
        # Generate html hash
        html_hash = hashlib.sha256(html.encode('utf-8')).hexdigest()

        # Check whether the html hash matches any other hash in the database.
        page_collision = await database_manager.check_pages_hash_collision(html_hash=html_hash)
        if page_collision is not None:
            original_page_id, original_site_id = page_collision
            await database_manager.save_page(page_id=page_id,
                                            status=status,
                                            site_id=original_site_id,
                                            page_type_code='DUPLICATE')
            await database_manager.add_page_link(original_page_id=original_page_id, duplicate_page_id=page_id)
            logger.info(f'Url {current_url} is a duplicate of another page.')
            return
    else:
        logger.debug(f'Page html is empty, this hopefully means that the page returned a binary file.')

    # Convert actual page url to canonical form
    page_url = ''.join(CrawlerHelper.canonicalize(set([url])))
    redirected = False
    # Check if URL is a redirect by matching current_url and returned url and the reassigning
    # Only checking HTTP response status for direct is most likely not enough since there could be a redirect with JS
    if current_url != page_url:
        # Page saves happen later in the execution, the important thing is the set the proper context (i.e. the url) for all the following operations
        logger.info(f'Current watched url {current_url} differs from actual browser url {page_url}. Redirect happened. Reassigning url.')
        redirected = True
        current_url = page_url
    else:
        logger.debug(f'Current watched url matches the actual browser url (i.e. no redirects happened).')

    # Parse url into a ParseResult object.
    current_url_parsed: ParseResult = urlparse(current_url)

    # Get url domain
    domain = current_url_parsed.netloc

    # Get site's ip address
    ip = CrawlerHelper.get_site_ip(hostname=domain)

    # If the DNS request failed it probably doesn't work.
    if ip is None:
        logger.info(f'DNS request failed for url {current_url}.')
        return

    # Get wait time between calls to the same domain and ip address
    wait_time = CrawlerHelper.get_site_wait_time(domain_available_times=domain_available_times, domain=domain,
                                                 ip_available_times=ip_available_times, ip=ip)
    if wait_time > 0:
        logger.debug(f'Required waiting time for the domain {domain} is {wait_time} seconds.')
        await asyncio.sleep(wait_time)
    else:
        logger.debug(f'Waiting for accessing the domain {domain} is not required.')

    # Get saved site from the database (if exists)
    saved_site = await database_manager.get_site(domain=domain)

    site_id: int
    if saved_site:
        # Don't request sitemaps if the domain was already visited
        sitemap_urls = set()
        logger.debug(f'Domain {domain} was already visited so sitemaps will be ignored.')
        site_id, domain, robots_content, sitemap_content = saved_site
        CrawlerHelper.load_saved_robots(robots_content=robots_content,
                                        robot_file_parser=robot_file_parser)
    else:
        logger.debug(f'Domain {domain} has not been visited yet.')
        CrawlerHelper.load_robots_file_url(parsed_url=current_url_parsed,
                                           robot_file_parser=robot_file_parser)
        sitemap_urls = await CrawlerHelper.find_sitemap_links(
            current_url=current_url_parsed,
            robot_file_parser=robot_file_parser,
            wait_time=wait_time)

        sitemap_content = None
        if robot_file_parser.site_maps() is not None:
            sitemap_content = ','.join(robot_file_parser.site_maps())
        site_id = await database_manager.save_site(domain=domain,
                                                   sitemap_content=sitemap_content,
                                                   robots_content=robot_file_parser.__str__())

    # PARSE PAGE
    # extract any relevant data from the page here, using BeautifulSoup
    beautiful_soup = BeautifulSoup(html, "html.parser")

    # get images
    page_images = CrawlerHelper.find_images(beautiful_soup)

    # get URLs
    page_urls = CrawlerHelper.find_links(beautiful_soup, current_url_parsed, robot_file_parser=robot_file_parser)

    # check page URLs for binary file link and place them in separate list
    (page_urls, page_data_entries) = CrawlerHelper.extract_binary_links(urls=page_urls)

    # SAVE PAGE
    # Check page content type for binary file
    if data_type is not None:
        # Save page as binary
        await database_manager.save_page(site_id=site_id, page_id=page_id, status=status, page_type_code='BINARY')
        # Save page data
        await database_manager.save_page_data(page_data_entries=[PageData(page_id=page_id, data_type_code=data_type)])
        logger.info(f'Crawling url {current_url} finished, because url leads to binary file {data_type}.')
        return

    # Check if page redirected
    if redirected:
        # Save original page as a redirect
        # TODO: what to do with html content? Since we do not have the content before the redirect.
        await database_manager.save_page(page_id=page_id,
                                         status=301,
                                         site_id=site_id)
        # Create new page to act as the current one
        page_id = await database_manager.create_empty_page(url=current_url, site_id=site_id)

    # Save page to the database
    await database_manager.save_page(page_id=page_id,
                                     html=html,
                                     status=status,
                                     site_id=site_id,
                                     html_hash=html_hash)

    # SAVE PAGE IMAGES
    # images saved here because of potential page_id change
    for image in page_images:
        image.page_id = page_id
    await database_manager.save_images(images=list(page_images))

    # SAVE PAGE DATA
    # page data saved here because of potential page_id change
    for page_data in page_data_entries:
        page_data.page_id = page_id
    await database_manager.save_page_data(page_data_entries=list(page_data_entries))

    # SAVE PAGE LINKS
    # combine DOM and sitemap URLs
    new_links = page_urls.union(sitemap_urls)
    # Add new urls to the frontier
    await database_manager.add_to_frontier(new_links)

    robot_delay = robot_file_parser.crawl_delay(USER_AGENT)
    CrawlerHelper.save_site_available_time(
        domain_available_times=domain_available_times,
        domain=domain,
        robot_delay=robot_delay,
        ip_available_times=ip_available_times,
        ip=ip)

    logger.info(f'Crawling url {current_url} finished.')


def entrypoint(*params):
    asyncio.run(run(*params))


async def run(database_manager: DatabaseManager, thread_number: int):
    """
    Setups the playwright library and starts the crawler.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, args=['--ignore-certificate-errors'])  # or "firefox" or "webkit".
        # create a new incognito browser context.
        context = await browser.new_context(ignore_https_errors=True, user_agent=USER_AGENT, )
        # create a new page in a pristine context.
        browser_page = await context.new_page()
        # Prevent loading some resources for better performance.
        await browser_page.route("**/*", CrawlerHelper.block_aggressively)
        robot_file_parser = urllib.robotparser.RobotFileParser()

        # TODO: maybe add an additional stop condition.
        while any(threads_status.values()):
            frontier_page = await database_manager.pop_frontier()
            if frontier_page is not None:
                threads_status[thread_number] = True
                frontier_id, url = frontier_page
                try:
                    await crawl_url(current_url=url,
                                    browser_page=browser_page,
                                    robot_file_parser=robot_file_parser,
                                    database_manager=database_manager,
                                    page_id=frontier_id)
                except Exception as e:
                    logger.critical(f'Crawling url {url} failed with an error {e}.')
                    # TODO: save status code
                    await database_manager.mark_page_as_failed(page_id=frontier_id)
                logger.info(f'Visited {await database_manager.get_visited_pages_count()} unique links.')
                logger.info(f'Frontier contains {len(await database_manager.get_frontier_links())} unique links.')
            else:
                threads_status[thread_number] = False
                logger.info('Sleeping.')
                await asyncio.sleep(30)

        await browser.close()
    logger.info(f'Thread {thread_number} finished.')


async def setup_threads(database_manager: DatabaseManager, n_threads: int = 5):
    threads: [Thread] = []
    for i in range(0, n_threads):
        threads_status[i] = True
        t = Thread(target=entrypoint, args=(database_manager, i), daemon=True, name=f'Spider {i}')
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
