import logging
from urllib.parse import ParseResult, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.async_api import Page
from url_normalize import url_normalize
from w3lib.url import url_query_cleaner
import requests
import re

from crawler_helper.constants import navigation_assign_regex, navigation_func_regex, USER_AGENT


class CrawlerHelper:

    @staticmethod
    async def get_page(url: str, page: Page) -> (str, int):
        """
        Requests and downloads a specific webpage.
        :param url: Webpage url to be crawled.
        :param page: Browser page.
        :return: html, status
        """
        response = await page.goto(url)
        await page.wait_for_timeout(2000)
        html = await page.content()
        status = response.status

        return html, status

    @staticmethod
    def extract_text(beautiful_soup: BeautifulSoup) -> str:
        """
        Get's verified HTML document and parses out only relevant text, which is then returned
        :param beautiful_soup: output of BeautifulSoup4 (i.e. validated and parsed HTML)
        """
        logging.debug(f'Extracting text from the page.')

        # kill all script and style elements
        for script in beautiful_soup(["script", "style"]):
            script.extract()
        # get text
        text = beautiful_soup.get_text()
        # break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text

    @staticmethod
    def find_links(beautiful_soup: BeautifulSoup, current_url: ParseResult, robot_file_parser: RobotFileParser):
        """
        Get's verified HTML document and finds all valid new URL holder elements, parses those URLs and returns them.
        :param robot_file_parser: parser for robots.txt
        :param current_url: website url to extract links from
        :param beautiful_soup:  output of BeautifulSoup4 (i.e. validated and parsed HTML)
        """
        logging.debug(f'Finding links on the page.')

        # find new URLs in DOM
        # select all valid navigatable elements
        clickables = beautiful_soup.select('a, [onclick]')
        new_urls = set()
        for element in clickables:
            url = None
            # check if current element is basic anchor tag or element with onclick listener
            href = element.get('href')
            if href is None:
                onclick = element.attr("onclick")
                # check for format when directly assinging
                if onclick.match(navigation_assign_regex):
                    url = re.search(navigation_assign_regex, onclick).group(3)
                # check for format when using function to assign
                elif onclick.match(navigation_func_regex):
                    url = re.search(navigation_func_regex, onclick).group(4)
            else:
                url = href

            # handle relative path URLs and fix them
            url = CrawlerHelper.fill_url(url, current_url)

            # check if allowed to visit
            if CrawlerHelper.is_allowed(url, robot_file_parser=robot_file_parser):
                new_urls.add(url)

        # find URLs from all sitemaps
        # check for sitemap.xml file and return the content as list(), otherwise None
        sitemap_urls = robot_file_parser.site_maps()
        if sitemap_urls is not None:
            for sitemap_url in sitemap_urls:
                # TODO: parse/fetch found sitemaps and add their URLs
                break

        # translate URLs to canonical form
        new_urls = CrawlerHelper.canonicalize(new_urls)

        return new_urls

    @staticmethod
    def canonicalize(urls: set):
        """
        Translates URLs into canonical form
        - adds missing schema, host, fix encodings, etc.
        - remove query parameters
        - remove element id selector from end of URL
        """
        logging.debug(f'Translating urls into a canonical form.')
        new_urls = set()
        for url in urls:
            u = url_normalize(url)
            u = url_query_cleaner(u)
            u = re.sub(r'#.*$', '', u)
            new_urls.add(u)
        return new_urls

    @staticmethod
    def is_allowed(url: str, robot_file_parser: RobotFileParser):
        """
        Checks if URL is allowed in page's robots.txt
        """
        logging.debug(f'Checkin whether url {url} is allowed.')
        if robot_file_parser is None or url is None:
            return True
        return robot_file_parser.can_fetch(USER_AGENT, url)

    @staticmethod
    def save_urls(urls: set, frontier: list):
        """
        Save new URLs to frontier
        """
        logging.debug('Saving urls.')
        for url in urls:
            # TODO: check if duplicate
            # TODO: add to frontier
            frontier.append(url)
            logging.info(f'Adding url {url} to frontier.')

    @staticmethod
    def fill_url(url: str, current_url_parsed: ParseResult):
        """
        Parameter url could be a full url or just a relative path (e.g. '/users/1', 'about.html', '/home')
        In such cases fill the rest of the URL and return
        """
        logging.debug(f'Filling url {url}.')
        url_parsed = urlparse(url)
        filled_url = url
        # check if full url
        if not url_parsed.scheme or not url_parsed.netloc:
            # take URL data from current page and append relative path
            filled_url = current_url_parsed.scheme + '://' + current_url_parsed.netloc + url
        return filled_url

    @staticmethod
    def get_real_url_from_shortlink(url: str):
        """
        Gets the full URL that is return by server in case of shortened URLs with missing schema and host, etc.
        'gov.si' -> 'https://www.gov.si'
        """
        logging.debug(f'Getting real url from the short url {url}.')
        resp = requests.get(url)
        return resp.url
