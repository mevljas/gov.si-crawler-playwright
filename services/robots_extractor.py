from urllib.parse import ParseResult
from urllib.robotparser import RobotFileParser

from logger.logger import logger
from services.delay_manager import refresh_site_available_time


async def load_robots_file_url(parsed_url: ParseResult, robot_file_parser: RobotFileParser, domain: str,
                               ip: str) -> None:
    """
    Finds and parser site's robots.txt file from an url.
    """
    robots_url = parsed_url.scheme + '://' + parsed_url.netloc + '/robots.txt'
    logger.debug(f'Getting robots.txt with url {robots_url}.')
    try:
        robot_file_parser.set_url(robots_url)
        # Wait required delay time
        await refresh_site_available_time(domain=domain, ip=ip)
        robot_file_parser.read()
    except:
        logger.debug(f'Getting robots.txt with url {robots_url} failed.')
        return None

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