import sys
import time
from typing import List, MutableMapping

from evcharge_status.models import Site, SiteDiff
from evcharge_status.notifications.file import Notifier
from evcharge_status.scraper import EVCharge
from evcharge_status.stores.file import Store


PERIOD = 600


def status():
    pass



def main(site_name):
    evcharge = EVCharge()
    file_store = Store('sites.json')
    notifier = Notifier()
    sites: MutableMapping[str, Site] = {
        site.guid: site
        for site in evcharge.search(site_name)
    }
    for site in sites.values():
        site.refresh_points()
        notifier.notify_state(site)
    file_store.put_sites(*sites.values())

    while True:
        time.sleep(PERIOD)
        updated_sites: MutableMapping[str, Site] = {}
        for guid, old_site in sites.items():
            new_site = old_site.copy()
            new_site.refresh_points()
            diff = SiteDiff.from_sites(old_site, new_site)
            if diff:
                updated_sites[guid] = new_site
                notifier.notify_changes(diff)

        if updated_sites:
            file_store.put_sites(*updated_sites.values())
            sites.update(updated_sites)


if __name__ == '__main__':
    main(sys.argv[1])