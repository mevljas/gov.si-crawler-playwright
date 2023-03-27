import asyncio
from threading import Thread

from common.globals import threads_status
from database.database_manager import DatabaseManager
from spider.spider import start_spiders


def entrypoint(*params):
    asyncio.run(start_spiders(*params))


async def setup_threads(database_manager: DatabaseManager, n_threads: int = 5):
    threads: [Thread] = []
    for i in range(0, n_threads):
        threads_status[i] = True
        t = Thread(target=entrypoint, args=(database_manager, i), daemon=True, name=f'Spider {i}')
        t.start()
        threads.append(t)
        # Don't start all threads at once so the site table get filled first.
        await asyncio.sleep(10)

    for t in threads:
        t.join()
