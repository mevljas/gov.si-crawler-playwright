import logging
import re
import time
import requests
from bs4 import BeautifulSoup
import urllib.request
from urllib.parse import urlparse
from urllib.parse import ParseResult
import urllib.robotparser as robotparser
from url_normalize import url_normalize
from w3lib.url import url_query_cleaner
import asyncio
from playwright.async_api import async_playwright

USER_AGENT = "fri-wier-besela"
DOMAIN_DELAY = 5  # seconds
seed_urls = ['gov.si', 'evem.gov.si', 'e-uprava.gov.si', 'e-prostor.gov.si']
robotparser = urllib.robotparser.RobotFileParser()
frontier = []  # keep track of not visited links
visited_links = set()  # keep track of visited links to avoid crawling them again
govsi_regex = re.compile(".*\.gov\.si$")  # regex to match URLs with the .gov.si domain
full_url_regex = re.compile("^http[s]+:\/\/.*\..*\.*")  # regex to match URL structure

"""
Regex to match JS redirect calls in format of e.g.: location.href = "/about.html". 
The URL is stored in group 3
"""
navigation_assign_regex = re.compile(".*(.)?location(.href)?\ =\ [\"\'](.*)[\"\']")

"""
Regex to match JS redirect calls in format of e.g.: location.assign('/about.html'). 
The URL is stored in group 4
"""
navigation_func_regex = re.compile(".*(.)?location(.href)?.(.*)\([\"\'](.*)[\"\']\)")


async def go_to_page(playwright, url: str):
    chromium = playwright.chromium  # or "firefox" or "webkit".
    # TODO: more efficient would be to open and close browser higher up in stack
    browser = await chromium.launch()
    page = await browser.new_page()

    response = await page.goto(url)
    await page.wait_for_timeout(2000)
    html = await page.content()
    status = response.status

    await browser.close()
    return html, status


async def crawl(current_url: str):
    logging.info(f'Crawling url {current_url}.')
    if not full_url_regex.match(current_url):
        current_url = get_real_url_from_shortlink(current_url)
    logging.debug('Url has to be cleaned.')
    current_url_parsed: ParseResult = urlparse(current_url)

    # skip crawling if URL is not from a .gov.si domain
    if not govsi_regex.match(current_url_parsed.netloc):
        logging.info('Url skipped because it is not from .gov.si.')
        return

    # check if URL is allowed by robots.txt rules
    robots_url = current_url_parsed.scheme + '://' + current_url_parsed.netloc + '/robots.txt'
    robotparser.set_url(robots_url)
    robotparser.read()
    if not is_allowed(current_url):
        logging.info('Url is not allowed in robots')
        return

    # TODO: check visited URLs from Frontier
    # skip crawling already visited links
    if current_url in visited_links:
        logging.info('Url is already in visited list.')
        return

    # TODO: incorporate delay for fetching pages in domain
    # TODO: save as column in site table
    delay = robotparser.crawl_delay(USER_AGENT)
    if delay is not None:
        DOMAIN_DELAY = delay

    # fetch page
    # TODO: incorporate check for different file types other than HTML (.pdf, .doc, .docx, .ppt, .pptx)
    # TODO: check and save http status
    async with async_playwright() as playwright:
        (html, status) = await go_to_page(playwright, current_url)

    # extract any relevant data from the page here, using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    content = extract_text(soup)
    urls = find_urls(soup, current_url_parsed)

    # TODO: check for duplicate page in Frontier
    # TODO: mark as visited in Frontier
    visited_links.add(current_url)
    # TODO: save page content
    # print(content)
    # TODO: save new URLs
    save_urls(urls)


def extract_text(soup):
    """
    Get's verified HTML document and parses out only relevant text, which is then returned
    :param soup - output of BeautifulSoup4 (i.e. validated and parsed HTML)
    """
    logging.debug(f'Extracting text from the page.')

    # kill all script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    # get text
    text = soup.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text


def find_urls(soup, current_url_parsed: ParseResult):
    """
    Get's verified HTML document and finds all valid new URL holder elements, parses those URLs and returns them.
    :param soup - output of BeautifulSoup4 (i.e. validated and parsed HTML)
    """
    logging.debug(f'Finding links on the page.')

    # find new URLs in DOM
    # select all valid navigatable elements
    clickables = soup.select('a, [onclick]')
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
        url = fill_url(url, current_url_parsed)

        # check if allowed to visit
        if is_allowed(url):
            new_urls.add(url)

    # find URLs from all sitemaps
    # check for sitemap.xml file and return the content as list(), otherwise None
    sitemap_urls = robotparser.site_maps()
    if sitemap_urls is not None:
        for sitemap_url in sitemap_urls:
            # TODO: parse/fetch found sitemaps and add their URLs
            break

    # translate URLs to canonical form
    new_urls = canonicalize(new_urls)

    return new_urls


def get_real_url_from_shortlink(url: str):
    """
    Gets the full URL that is return by server in case of shortened URLs with missing schema and host, etc.
    'gov.si' -> 'https://www.gov.si'
    """
    logging.debug(f'Getting real url from the short url {url}.')
    resp = requests.get(url)
    return resp.url


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


def is_allowed(url: str):
    """
    Checks if URL is allowed in page's robots.txt
    """
    logging.debug(f'Checkin whether url {url} is allowed.')
    if robotparser is None or url is None:
        return True
    return robotparser.can_fetch(USER_AGENT, url)


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


def save_urls(urls: set):
    """
    Save new URLs to frontier
    """
    logging.debug('Saving urls.')
    for url in urls:
        # TODO: check if duplicate
        # TODO: add to frontier
        frontier.append(url)
        print(url)

# TODO: incorporate seed URLs
# TODO: implement multi-threading with database locking
# start crawling from each seed URL
# for seed_url in seed_urls:
#    crawl(seed_url)
