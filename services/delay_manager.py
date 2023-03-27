import asyncio
from time import time

from common.constants import DEFAULT_DOMAIN_DELAY
from common.globals import domain_available_times, ip_available_times, lock
from logger.logger import logger


def save_site_available_time(
        delay: int,
        domain: str,
        ip: str):
    """
    Save the time in seconds when the domain and ip will be available for crawling again.
    """
    logger.debug(f'Saving delay {delay} seconds for the domain {domain} and ip {ip}.')
    # read or write the shared variable
    domain_available_times[domain] = time() + delay
    if ip is not None:
        ip_available_times[ip] = time() + delay


def get_site_wait_time(domain: str, ip: str):
    """
    Get the wait time in seconds for the domain and ip to be available for crawling again.
    """
    current_time = time()
    # read or write the shared variable
    domain_delay = (domain_available_times.get(domain) or current_time) - current_time
    if ip is not None:
        ip_delay = (ip_available_times.get(ip) or current_time) - current_time
    else:
        ip_delay = -1
    max_delay = max(domain_delay, ip_delay)
    logger.debug(f'Required delay for the domain {domain} and ip {ip} is {max_delay} seconds.')
    return max_delay


async def refresh_site_available_time(
        domain: str,
        ip: str,
        robot_delay: str = None):
    """
    Waits the required delay time and refreshes
    the wait time in seconds for the domain and ip to be available for crawling again.
    """
    logger.debug(f'Robots.txt delay is {robot_delay}.')
    required_delay = int(robot_delay) if robot_delay is not None else DEFAULT_DOMAIN_DELAY
    # acquire the lock
    with lock:
        wait_time = get_site_wait_time(domain=domain, ip=ip)
        wait_time = wait_time if wait_time > 0 else 0
        save_site_available_time(domain=domain, ip=ip, delay=required_delay + wait_time)
    if wait_time > 0:
        logger.debug(f'Required waiting time for the domain {domain} and ip {ip} is {wait_time} seconds.')
        await asyncio.sleep(wait_time)
    else:
        logger.debug(f'Waiting for accessing the domain {domain} and ip {ip} is not required.')
