import asyncio
from typing import Iterable, MutableMapping

from .models import Site, SiteDiff


async def watcher(sites: Iterable[Site], period: float, store, notifier):
    sites_memory_store: MutableMapping[str, Site] = {
        site.guid: site for site in sites
    }
    while True:
        awaitables = []
        updated_sites: MutableMapping[str, Site] = {}
        for guid, site in sites_memory_store.items():
            old_site = site.copy()
            await site.refresh_points()
            diff = SiteDiff.from_sites(old_site, site)
            if diff:
                updated_sites[guid] = site
                awaitables.append(notifier.notify_changes(diff))

        if updated_sites:
            awaitables.append(store.put_sites(*updated_sites.values()))

        await asyncio.gather(asyncio.sleep(period), *awaitables)