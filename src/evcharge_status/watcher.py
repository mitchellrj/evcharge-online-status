import asyncio
import threading
from typing import Iterable, MutableMapping

from .models import Site, SiteDiff
from .notifications import NotifierType
from .stores import StoreType



class Watcher:

    period: float
    notifier: NotifierType
    store: StoreType
    _exit_semaphore: threading.Semaphore
    _sites_memory_store: MutableMapping[str, Site]

    def __init__(self, sites: Iterable[Site], period: float, store: StoreType, notifier: NotifierType):
        self.period = period
        self.store = store
        self.notifier = notifier
        self._exit_semaphore = threading.Semaphore(0)
        self._sites_memory_store = {
            site.guid: site for site in sites
        }
        self.__sleep_task = None

    async def _sleep(self, period: float):
        coro = asyncio.sleep(period)
        self.__sleep_task = asyncio.ensure_future(coro)
        try:
            await self.__sleep_task
        except asyncio.CancelledError:
            pass
        self.__sleep_task = None

    async def __aenter__(self):
        await self._sleep(self.period)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def stop(self):
        self._exit_semaphore.release()
        if self.__sleep_task:
            self.__sleep_task.cancel()

    async def run(self):
        while not self._exit_semaphore.acquire(blocking=False):
            awaitables = []
            updated_sites: MutableMapping[str, Site] = {}
            for guid, site in self._sites_memory_store.items():
                old_site = site.copy()
                await site.refresh_points()
                diff = SiteDiff.from_sites(old_site, site)
                if diff:
                    updated_sites[guid] = site
                    awaitables.append(self.notifier.notify_changes(diff))

            if updated_sites:
                awaitables.append(self.store.put_sites(*updated_sites.values()))

            await asyncio.gather(self._sleep(self.period), *awaitables)