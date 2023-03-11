import asyncio
import logging
import urllib.robotparser
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from crawler_helper.constants import USER_AGENT, default_domain_delay
from crawler_helper.crawler_helper import CrawlerHelper

already_visited_links = set() # keep track of visited links to avoid crawling them again
frontier = set()  # keep track of not visited links
# seed_urls = {'https://gov.si', 'https://evem.gov.si', 'https://e-uprava.gov.si', 'https://e-prostor.gov.si'}
seed_urls = {'https://e-prostor.gov.si'}


async def crawl_url(current_url: str, page: Page, robot_file_parser: RobotFileParser):
    """
    Crawls the provided current_url.
    :param current_url: Url to be crawled
    :param page: Browser page
    :param robot_file_parser: parser for robots.txt
    :return:
    """
    logging.info(f'Crawling url {current_url} started.')

    # TODO: mark as visited in Frontier
    already_visited_links.add(current_url)

    # Fix shortened URLs (if necessary).
    current_url = CrawlerHelper.fix_shortened_url(url=current_url)

    # Parse url into a ParseResult object.
    current_url_parsed: ParseResult = urlparse(current_url)

    # get robots.txt
    CrawlerHelper.load_robots_file(parsed_url=current_url_parsed, robot_file_parser=robot_file_parser)

    # fetch page
    # TODO: incorporate check for different file types other than HTML (.pdf, .doc, .docx, .ppt, .pptx)
    # TODO: check and save http status
    (html, status) = await CrawlerHelper.get_page(url=current_url, page=page)

    # extract any relevant data from the page here, using BeautifulSoup
    beautiful_soup = BeautifulSoup(html, "html.parser")

    # get content
    content = CrawlerHelper.extract_text(beautiful_soup)

    # get URLs
    page_urls = CrawlerHelper.find_links(beautiful_soup, current_url_parsed, robot_file_parser=robot_file_parser)
    sitemap_urls = CrawlerHelper.find_sitemap_links(current_url_parsed, robot_file_parser=robot_file_parser)

    # combine DOM and sitemap URLs
    new_links = page_urls.union(sitemap_urls)

    # skip crawling already visited links
    new_links = new_links - already_visited_links

    # Filter urls
    new_links = CrawlerHelper.filter_not_allowed_urls(urls=new_links, robot_file_parser=robot_file_parser)



    # TODO: check for duplicate page in Frontier

    # TODO: save page content
    # print(content)
    # TODO: save new URLs
    CrawlerHelper.save_urls(urls=new_links, frontier=frontier)
    logging.info(f'Crawling url {current_url} finished.')

    # TODO: incorporate delay for fetching pages in domain
    # TODO: save as column in site table?
    robot_delay = robot_file_parser.crawl_delay(USER_AGENT)
    # TODO: set delay in crawler instance?
    if robot_delay:
        await asyncio.sleep(int(robot_delay))
    else:
        await asyncio.sleep(default_domain_delay)


async def start_crawler():
    """
    Setups the playwright library and starts the crawler.
    """
    logging.info(f'Starting the crawler.')
    async with async_playwright() as playwright:
        chromium = playwright.chromium  # or "firefox" or "webkit".
        browser = await chromium.launch()
        page = await browser.new_page()
        robot_file_parser = urllib.robotparser.RobotFileParser()
        while seed_urls:  # While seed list is not empty
            for url in list(seed_urls):
                await crawl_url(current_url=url, page=page, robot_file_parser=robot_file_parser)
                seed_urls.remove(url)
                break

        await browser.close()
    logging.info(f'Crawler finished.')
