import re
import asyncio
import os
import socket
from time import time
from datetime import datetime, timezone
from urllib.parse import ParseResult, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from database.models import Image
from playwright.async_api import Page
from url_normalize import url_normalize
from w3lib.url import url_query_cleaner

from crawler_helper.constants import navigation_assign_regex, navigation_func_regex, USER_AGENT, govsi_regex, \
    full_url_regex, default_domain_delay, excluded_resource_types, relative_url_regex, image_extensions
from logger.logger import logger


class CrawlerHelper:

    @staticmethod
    async def get_page(url: str, page: Page) -> (str, str, int):
        """
        Requests and downloads a specific webpage.
        :param url: Webpage url to be crawled.
        :param page: Browser page.
        :return: html, status
        """
        logger.debug(f'Opening page {url}.')
        response = await page.goto(url, timeout=10000)
        html = await page.content()
        status = response.status
        logger.debug(f'Response status is {status}.')
        return page.url, html, status

    @staticmethod
    def find_links(beautiful_soup: BeautifulSoup, current_url: ParseResult, robot_file_parser: RobotFileParser) -> set[
        str]:
        """
        Get's verified HTML document and finds all valid new URL holder elements, parses those URLs and returns them.
        :param robot_file_parser: parser for robots.txt
        :param current_url: website url to extract links from
        :param beautiful_soup:  output of BeautifulSoup4 (i.e. validated and parsed HTML)
        """
        logger.debug(f'Finding links on the page.')

        # find new URLs in DOM
        # select all valid navigatable elements
        clickables = beautiful_soup.select('a, [onclick]')
        new_urls = set()
        for element in clickables:
            url = None
            # check if current element is basic anchor tag or element with onclick listener
            href = element.attrs.get('href')
            onclick = element.attrs.get('onclick')
            if href is not None and CrawlerHelper.is_url(href):
                url = href
            elif onclick is not None:
                # check for format when directly assinging
                if navigation_assign_regex.match(onclick):
                    url = re.search(navigation_assign_regex, onclick).group(3)
                # check for format when using function to assign
                elif navigation_func_regex.match(onclick):
                    url = re.search(navigation_func_regex, onclick).group(4)
            else:
                continue

            # continue if no valid url was found
            if url is None: continue

            # handle relative path URLs and fix them
            url = CrawlerHelper.fill_url(url, current_url)

            # check if the url is allowed to visit
            if CrawlerHelper.is_url_allowed(url, robot_file_parser=robot_file_parser) \
                    and CrawlerHelper.is_domain_allowed(url=url):
                new_urls.add(url)

        # translate URLs to canonical form
        new_urls = CrawlerHelper.canonicalize(new_urls)

        return new_urls

    @staticmethod
    def find_images(beautiful_soup: BeautifulSoup) -> set[Image]:
        """
        Get's verified HTML document and finds all images and returns them.
        :param beautiful_soup:  output of BeautifulSoup4 (i.e. validated and parsed HTML)
        """
        logger.debug(f'Finding images on the page.')
        accessed_time = CrawlerHelper.get_iso_timestamp()

        # find img tags in DOM
        imgs = beautiful_soup.select('img')
        images = set()
        for img in imgs:
            src = img.attrs.get('src')

            # Extract the path component of the URL
            path = urlparse(src).path
            # Split the path into filename and extension
            name, ext = os.path.splitext(os.path.basename(path))

            # Check if the URL is a data URI
            # Example: src='data:image/png;base64,iVBORw0[...]uQmCC'
            if src.startswith('data:image'):
                filename = None
                extension = src.split(';')[0].split('/')[-1]
            # Parse the URL and check if it has a valid file extension
            elif ext.lower() in image_extensions:
                filename = name
                extension = ext[1:]  # remove the dot from the extension
            else:
                continue

                # TODO: add page_id
            image: Image = Image(filename=filename, content_type=extension, accessed_time=accessed_time)
            images.add(image)
        return images

    @staticmethod
    async def find_sitemap_links(current_url: ParseResult, robot_file_parser: RobotFileParser, wait_time: int) -> set[
        str]:
        """
        Checks for sitemap.xml file and recursively traverses the tree to find all URLs.
        :param robot_file_parser: parser for robots.txt
        :param current_url: website url to extract links from
        """
        logger.debug(f'Finding urls from sitemaps.')
        # find URLs from all sitemaps
        # check for sitemap.xml file and return the content as list(), otherwise None
        sitemaps = robot_file_parser.site_maps()
        new_urls_sitemap = set()
        if sitemaps is not None:
            for sitemap in sitemaps:
                # parse/fetch found sitemaps and add their URLs
                new_urls_sitemap.update(await CrawlerHelper.get_sitemap_urls(CrawlerHelper, sitemap))
        else:
            # even though sitemap is not in robots.txt, try to find it in root
            sitemap = current_url.scheme + '://' + current_url.netloc + '/sitemap.xml'
            new_urls_sitemap.update(await CrawlerHelper.get_sitemap_urls(CrawlerHelper, sitemap))

        # translate URLs to canonical form
        new_urls_sitemap = CrawlerHelper.canonicalize(new_urls_sitemap)

        return new_urls_sitemap

    @staticmethod
    async def get_sitemap_urls(self, sitemap_url, new_urls=None, wait_time: int = default_domain_delay) -> set[str]:
        """
        From given root sitemap url, visting all .xml child routes and return leaf nodes as a new set of URLs
        This is a recursive function.
        """
        logger.debug(f'Sleeping for {wait_time}.')
        await asyncio.sleep(wait_time)
        logger.debug(f'Looking at sitemap {sitemap_url} for new urls.')
        sitemap = requests.get(sitemap_url)
        if sitemap.status_code != 200:
            return new_urls if new_urls != None else set()

        try:
            xml = BeautifulSoup(sitemap.content, "xml")
        except:
            return new_urls if new_urls != None else set()

        if new_urls is None:
            new_urls = set()

        for loc in xml.find_all('loc'):
            url = loc.get_text()

            if url.endswith('.xml') or 'sitemap.xml' in url:
                new_urls.update(await self.get_sitemap_urls(self, url, new_urls))
            else:
                new_urls.add(url)

        return new_urls

    @staticmethod
    def delay() -> None:
        """
        Wait web crawler delay. Not to be used for playwright!
        """
        logger.debug(f'Delay for {CrawlerHelper.domain_delay} seconds')
        time.sleep(CrawlerHelper.domain_delay)
        return None

    @staticmethod
    def canonicalize(urls: set) -> set[str]:
        """
        Translates URLs into canonical form
        - adds missing schema, host, fix encodings, etc.
        - remove query parameters
        - remove element id selector from end of URL
        """
        logger.debug(f'Translating urls into a canonical form.')
        new_urls = set()
        for url in urls:
            u = url_normalize(url)  # general form fixes
            u = url_query_cleaner(u)  # remove query params
            u = re.sub(r'#.*$', '', u)  # remove fragment
            # end with / if not a filetype
            if not (CrawlerHelper.has_file_extension(u) or u.endswith('/')):
                u += '/'
            new_urls.add(u)
        return new_urls

    @staticmethod
    def has_file_extension(url) -> bool:
        """
        Checks if URL end with a file extenstion like: .html, .pdf, .txt, etc.
        """
        logger.debug(f'Checking whether url {url} points to file.')
        pattern = r'^.*\/[^\/]+\.[^\/]+$'
        return bool(re.match(pattern, url))

    @staticmethod
    def is_url_allowed(url: str, robot_file_parser: RobotFileParser) -> bool:
        """
        Checks if URL is allowed in page's robots.txt
        """
        logger.debug(f'Checking whether url {url} is allowed in robots.txt.')
        if robot_file_parser is None:
            allowed = True
        else:
            allowed = robot_file_parser.can_fetch(USER_AGENT, url)
        logger.debug(f'Url {url} allowed in robots.txt: {allowed}.')
        return allowed

    @staticmethod
    def is_url(url) -> bool:
        """
        Checks if string is URL. It should return true for full URLs and also for partial (e.g. /about/me, #about, etc.)
        """
        logger.debug(f'Checking whether potential url {url} is of valid format.')
        if url is None:
            return False
        try:
            result = urlparse(url)
            if result.scheme and result.scheme not in ['http', 'https']:
                return False
            return bool(result.netloc or result.path or result.fragment)
        except:
            return False

    @staticmethod
    def save_urls(urls: set[str], frontier: set[str]):
        """
        Save new URLs to frontier
        """
        logger.debug('Saving urls.')
        url_list = list(urls)
        for url in url_list:
            # TODO: check if duplicate
            # TODO: add to frontier
            frontier.add(url)
            logger.debug(f'Adding url {url} to frontier.')
        logger.info(f'Saved {len(url_list)} urls.')

    @staticmethod
    def fill_url(url: str, current_url_parsed: ParseResult) -> str:
        """
        Parameter url could be a full url or just a relative path (e.g. '/users/1', 'about.html', '/home')
        In such cases fill the rest of the URL and return
        """
        logger.debug(f'Filling url {url}.')
        url_parsed = urlparse(url)
        filled_url = url
        # check if full url
        if not url_parsed.scheme or not url_parsed.netloc:
            # take URL data from current page and append relative path
            filled_url = current_url_parsed.scheme + '://' + current_url_parsed.netloc + url
        return filled_url

    @staticmethod
    def get_real_url_from_shortlink(url: str) -> str:
        """
        Gets the full URL that is return by server in case of shortened URLs with missing schema and host, etc.
        'gov.si' -> 'https://www.gov.si'
        """
        logger.debug(f'Getting real url from the short url {url}.')
        try:
            resp = requests.get(url)
        except:
            return url
        return resp.url

    @staticmethod
    def is_domain_allowed(url: str) -> bool:
        """
        Checks whether the domain is on the allowed list.
        """
        logger.debug(f'Checking wheter {url} is on the domain allowed list.')
        url_parsed = urlparse(url)
        allowed = govsi_regex.match(url_parsed.netloc)
        logger.debug(f'Url {url} domain allowed: {allowed}.')
        return allowed

    @staticmethod
    def fix_shortened_url(url: str) -> str:
        """
        Fix shortened url if necessary. 
        Also transform into canonical form to then compare to actual url in browser.
        """
        if not full_url_regex.match(url):
            logger.debug('Url has to be cleaned.')
            return CrawlerHelper.get_real_url_from_shortlink(url=url)
        logger.debug('Url doesnt have to be cleaned.')
        return url

    @staticmethod
    def get_base_url(url: str) -> str:
        """
        Get base url. 
        """
        logger.debug(f'Converting {url} to base url.')
        parsed_url: ParseResult = urlparse(url)
        return parsed_url.scheme + '://' + parsed_url.netloc + '/'

    @staticmethod
    def load_robots_file_url(parsed_url: ParseResult, robot_file_parser: RobotFileParser) -> None:
        """
        Finds and parser site's robots.txt file from an url.
        """
        robots_url = parsed_url.scheme + '://' + parsed_url.netloc + '/robots.txt'
        logger.debug(f'Getting robots.txt with url {robots_url}.')
        try:
            robot_file_parser.set_url(robots_url)
            robot_file_parser.read()
        except:
            logger.warning(f'Getting robots.txt with url {robots_url} failed.')
            return None

    @staticmethod
    def load_saved_robots(robots_content: str, robot_file_parser: RobotFileParser) -> None:
        """
        Loads saved site's robots.txt.
        """
        logger.debug('Loading saved robots.txt.')
        try:
            robot_file_parser.parse(robots_content)
        except:
            logger.warning(f'Loading saved robots.txt failed.')
            return None

    @staticmethod
    def save_site_available_time(
            domain_available_times: dict,
            ip_available_times: dict,
            robot_delay: str,
            domain: str,
            ip: str):
        """
        Save the time in seconds when the domain and ip will be available for crawling again.
        """
        delay = int(robot_delay) if robot_delay is not None else default_domain_delay
        logger.debug(f'Saving delay {delay} seconds for the domain {domain} and ip {ip}.')
        domain_available_times[domain] = time() + delay
        if ip is not None:
            ip_available_times[ip] = time() + delay

    @staticmethod
    def get_site_wait_time(domain_available_times: dict, ip_available_times: dict, domain: str, ip: str):
        """
        Get the wait time in seconds for the domain an ip to be available for crawling again.
        """
        current_time = time()
        domain_delay = (domain_available_times.get(domain) or current_time) - current_time
        if ip is not None:
            ip_delay = (ip_available_times.get(ip) or current_time) - current_time
        else:
            ip_delay = -1
        max_delay = max(domain_delay, ip_delay)
        logger.debug(f'Required delay for the domain {domain} and ip {ip} is {max_delay} seconds.')
        return max_delay

    @staticmethod
    async def block_aggressively(route):
        """
        Prevent loading some resources for better performance.
        """
        if route.request.resource_type in excluded_resource_types:
            await route.abort()
        else:
            await route.continue_()

    @staticmethod
    def get_site_ip(hostname: str):
        """
        Returns site's ip address.
        """
        try:
            return socket.gethostbyname(hostname)
        except:
            logger.warning(f'Getting site ip address failed.')
            return None

    @staticmethod
    def get_iso_timestamp() -> datetime:
        """
        Returns current UTC timestamp in ISO format.
        """
        return datetime.now(timezone.utc)
