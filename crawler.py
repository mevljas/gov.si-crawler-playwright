import asyncio
import urllib.robotparser
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from crawler_helper.constants import USER_AGENT
from crawler_helper.crawler_helper import CrawlerHelper
from logger.logger import logger

already_visited_links = set()  # keep track of visited links to avoid crawling them again
frontier = set()  # keep track of not visited links
seed_urls = {'https://gov.si', 'https://evem.gov.si', 'https://e-uprava.gov.si', 'https://e-prostor.gov.si'}
domain_available_times = {}  # A set with domains next available times.
ip_available_times = {}  # A set with ip next available times.


async def crawl_url(current_url: str, page: Page, robot_file_parser: RobotFileParser):
    """
    Crawls the provided current_url.
    :param current_url: Url to be crawled
    :param page: Browser page
    :param robot_file_parser: parser for robots.txt
    :return:
    """
    logger.info(f'Crawling url {current_url} started.')

    # Fix shortened URLs (if necessary).
    current_url = CrawlerHelper.fix_shortened_url(url=current_url)

    # fetch page
    # TODO: incorporate check for different file types other than HTML (.pdf, .doc, .docx, .ppt, .pptx)
    try:
        (url, html, status) = await CrawlerHelper.get_page(url=current_url, page=page)
    except Exception as e:
        logger.warning(f'Opening page {current_url} failed with an error {e}.')
        return

    # Convert actual page url to base/root url format
    base_page_url = CrawlerHelper.get_base_url(url)
    # Check if URL is a redirect by matching current_url and returned url and the reassigning
    if current_url != base_page_url:
        current_url = base_page_url
        logger.debug(f'Current watched url {current_url} differs from actual browser url {base_page_url}. Redirect happened. Reassigning url.')
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
        return

    # Get wait time between calls to the same domain and ip address
    wait_time = CrawlerHelper.get_site_wait_time(domain_available_times=domain_available_times, domain=domain, ip_available_times=ip_available_times, ip=ip)
    if wait_time > 0:
        logger.debug(f'Required waiting time for the domain {domain} is {wait_time} seconds.')
        await asyncio.sleep(wait_time)
    else:
        logger.debug(f'Waiting for accessing the domain {domain} is not required.')

    # TODO: mark as visited in Frontier

    # get robots.txt
    CrawlerHelper.load_robots_file(parsed_url=current_url_parsed, robot_file_parser=robot_file_parser)

    # extract any relevant data from the page here, using BeautifulSoup
    beautiful_soup = BeautifulSoup(html, "html.parser")

    # get URLs
    page_urls = CrawlerHelper.find_links(beautiful_soup, current_url_parsed, robot_file_parser=robot_file_parser)

    # get images
    page_images = CrawlerHelper.find_images(beautiful_soup)

    # Don't request sitemaps if the domain was already visited
    if domain not in domain_available_times.keys():
        sitemap_urls = CrawlerHelper.find_sitemap_links(current_url_parsed, robot_file_parser=robot_file_parser, wait_time=wait_time)
    else:
        sitemap_urls = set()
        logger.debug(f'Domain {domain} was already visited so sitemaps will be ignored.')

    # combine DOM and sitemap URLs
    new_links = page_urls.union(sitemap_urls)

    # skip crawling already visited links
    new_links = new_links - already_visited_links

    # TODO: check for duplicate page in Frontier

    # TODO: save page
    # TODO: save new URLs
    # CrawlerHelper.save_urls(urls=new_links, frontier=frontier)
    seed_urls.update(new_links)

    robot_delay = robot_file_parser.crawl_delay(USER_AGENT)
    CrawlerHelper.save_site_available_time(domain_available_times=domain_available_times, domain=domain,
                                           robot_delay=robot_delay, ip_available_times=ip_available_times, ip=ip)

    logger.info(f'Crawling url {current_url} finished.')


async def start_crawler():
    """
    Setups the playwright library and starts the crawler.
    """
    logger.info(f'Starting the crawler.')
    async with async_playwright() as playwright:
        chromium = playwright.chromium  # or "firefox" or "webkit".
        browser = await chromium.launch()
        page = await browser.new_page()
        # Prevent loading some resources for better performance.
        await page.route("**/*", CrawlerHelper.block_aggressively)
        robot_file_parser = urllib.robotparser.RobotFileParser()

        while seed_urls:  # While seed list is not empty
            for url in list(seed_urls):
                try:
                    await crawl_url(current_url=url, page=page, robot_file_parser=robot_file_parser)
                except Exception as e:
                    logger.critical(f'Crawling url {url} failed with an error {e}.')
                already_visited_links.add(url)
                seed_urls.remove(url)
                logger.info('###########################################################################')
                logger.info(f'Already visited {len(already_visited_links)} unique links.')
                logger.info(f'Will visit additional {len(seed_urls)} unique links.')
                logger.info('###########################################################################')

        await browser.close()
    logger.info(f'Crawler finished.')
