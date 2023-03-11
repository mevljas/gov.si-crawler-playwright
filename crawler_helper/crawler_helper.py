import logging
from urllib.parse import ParseResult, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.async_api import Page
from url_normalize import url_normalize
from w3lib.url import url_query_cleaner
import requests
import re
import time

from crawler_helper.constants import navigation_assign_regex, navigation_func_regex, USER_AGENT, govsi_regex


class CrawlerHelper:
    domain_delay = 5  # seconds

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
    def find_links(beautiful_soup: BeautifulSoup, current_url: ParseResult, robot_file_parser: RobotFileParser) ->  set[str]:
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

            # check if allowed to visit
            if CrawlerHelper.is_url_allowed(url, robot_file_parser=robot_file_parser):
                new_urls.add(url)

        # translate URLs to canonical form
        new_urls = CrawlerHelper.canonicalize(new_urls)

        return new_urls

    @staticmethod
    def find_sitemap_links(current_url: ParseResult, robot_file_parser: RobotFileParser) ->  set[str]:
        """
        Checks for sitemap.xml file and recursively traverses the tree to find all URLs.
        :param robot_file_parser: parser for robots.txt
        :param current_url: website url to extract links from
        """
        logging.debug(f'Finding urls from sitemaps.')
        # find URLs from all sitemaps
        # check for sitemap.xml file and return the content as list(), otherwise None
        sitemaps = robot_file_parser.site_maps()
        new_urls_sitemap = set()
        if sitemaps is not None:
            for sitemap in sitemaps:
                # parse/fetch found sitemaps and add their URLs
                new_urls_sitemap.update(CrawlerHelper.get_sitemap_urls(CrawlerHelper, sitemap))
        else:
            # even though sitemap is not in robots.txt, try to find it in root
            sitemap = current_url.scheme + '://' + current_url.netloc + '/sitemap.xml'
            new_urls_sitemap.update(CrawlerHelper.get_sitemap_urls(CrawlerHelper, sitemap))

        # translate URLs to canonical form
        new_urls_sitemap = CrawlerHelper.canonicalize(new_urls_sitemap)

        return new_urls_sitemap

    @staticmethod
    def get_sitemap_urls(self, sitemap_url, new_urls=None) -> set[str]:
        """
        From given root sitemap url, visting all .xml child routes and return leaf nodes as a new set of URLs
        This is a recursive function.
        """
        CrawlerHelper.delay()
        logging.debug(f'Looking at sitemap {sitemap_url} for new urls.')
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
                new_urls.update(self.get_sitemap_urls(self, url, new_urls))
            else:
                new_urls.add(url)

        return new_urls

    @staticmethod
    def delay() -> None:
        """
        Wait web crawler delay. Not to be used for playwright!
        """
        logging.debug(f'Delay for {CrawlerHelper.domain_delay} seconds')
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
        logging.debug(f'Translating urls into a canonical form.')
        new_urls = set()
        for url in urls:
            u = url_normalize(url)  # general form fixes
            u = url_query_cleaner(u)  # remove query params
            u = re.sub(r'#.*$', '', u)  # remove fragment
            # add 'www' subdomain
            if 'www' not in u and '://' in u:
                protocol_end = u.index('://') + 3
                u = u[:protocol_end] + 'www.' + url[protocol_end:]
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
        logging.debug(f'Checking whether url {url} points to file.')
        pattern = r'^.*\/[^\/]+\.[^\/]+$'
        return bool(re.match(pattern, url))

    @staticmethod
    def is_url_allowed(url: str, robot_file_parser: RobotFileParser) -> bool:
        """
        Checks if URL is allowed in page's robots.txt
        """
        logging.debug(f'Checking whether url {url} is allowed.')
        if robot_file_parser is None or url is None:
            return True
        return robot_file_parser.can_fetch(USER_AGENT, url)

    @staticmethod
    def is_url(url) -> bool:
        """
        Checks if string is URL. It should return true for full URLs and also for partial (e.g. /about/me, #about, etc.)
        """
        logging.debug(f'Checking whether potential url {url} is of valid format.')
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
    def save_urls(urls: set, frontier: list):
        """
        Save new URLs to frontier
        """
        logging.debug('Saving urls.')
        for url in urls:
            # TODO: check if gov.si domain
            # TODO: check if duplicate
            # TODO: add to frontier
            frontier.append(url)
            logging.info(f'Adding url {url} to frontier.')

    @staticmethod
    def fill_url(url: str, current_url_parsed: ParseResult) -> str:
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
    def get_real_url_from_shortlink(url: str) -> str:
        """
        Gets the full URL that is return by server in case of shortened URLs with missing schema and host, etc.
        'gov.si' -> 'https://www.gov.si'
        """
        logging.debug(f'Getting real url from the short url {url}.')
        try:
            resp = requests.get(url)
        except:
            return url
        return resp.url

    @staticmethod
    def is_allowed_domain(url: ParseResult) -> bool:
        """
        Checks whether the domain is on the allowed list.
        """
        return govsi_regex.match(url.netloc)
