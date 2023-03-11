import logging
import re
import urllib.robotparser

from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from crawler_helper.constants import full_url_regex, USER_AGENT
from crawler_helper.crawler_helper import CrawlerHelper

visited_links = set()  # keep track of visited links to avoid crawling them again
frontier = []  # keep track of not visited links
seed_urls = ['gov.si', 'evem.gov.si', 'e-uprava.gov.si', 'e-prostor.gov.si']


async def crawl_url(current_url: str, page: Page, robot_file_parser: RobotFileParser, ):
    """
    Crawls the provided current_url.
    :param robot_file_parser: parser for robots.txt
    :param current_url: Url to be crawled
    :param page: Browser page
    :return:
    """
    logging.info(f'Crawling url {current_url}.')
    
    # just in case fill in any shortened URLs
    if not full_url_regex.match(current_url):
        logging.debug('Url has to be cleaned.')
        current_url = CrawlerHelper.get_real_url_from_shortlink(current_url)
    current_url_parsed: ParseResult = urlparse(current_url)

    # skip crawling if URL is not from a .gov.si domain
    if not CrawlerHelper.is_allowed_domain(url=current_url_parsed):
        logging.info('Url skipped because it is not from .gov.si.')
        return

    # get robots.txt
    robots_url = current_url_parsed.scheme + '://' + current_url_parsed.netloc + '/robots.txt'
    robot_file_parser.set_url(robots_url)
    robot_file_parser.read()

    # check if URL is allowed by robots.txt rules
    if not CrawlerHelper.is_url_allowed(current_url, robot_file_parser=robot_file_parser):
        logging.info('Url is not allowed in robots')
        return

    # TODO: check visited URLs from Frontier
    # skip crawling already visited links
    if current_url in visited_links:
        logging.info('Url is already in visited list.')
        return

    # TODO: incorporate delay for fetching pages in domain
    # TODO: save as column in site table?
    delay = robot_file_parser.crawl_delay(USER_AGENT)
    if delay is not None:
        # TODO: set delay in crawler instance?
        delay

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
    all_urls = page_urls.union(sitemap_urls)

    # TODO: check for duplicate page in Frontier
    # TODO: mark as visited in Frontier
    visited_links.add(current_url)
    # TODO: save page content
    # print(content)
    # TODO: save new URLs
    CrawlerHelper.save_urls(urls=all_urls, frontier=frontier)


async def start_crawler(start_url: str):
    """
    Setups the playwright library and starts the crawler.
    :param start_url: First url to be crawled
    """
    logging.info(f'Starting the crawler with an url {start_url}.')
    robot_file_parser = urllib.robotparser.RobotFileParser()
    async with async_playwright() as playwright:
        chromium = playwright.chromium  # or "firefox" or "webkit".
        browser = await chromium.launch()
        page = await browser.new_page()
        await crawl_url(current_url=start_url, page=page, robot_file_parser=robot_file_parser)

        await browser.close()
    logging.info(f'Crawler finished.')
