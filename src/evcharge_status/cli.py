import argparse
import asyncio
import signal
import sys

from evcharge_status.notifications.file import Notifier
from evcharge_status.scraper import EVCharge
from evcharge_status.stores import get_store
from evcharge_status.watcher import watcher


def get_argument_parser():
    parser = argparse.ArgumentParser(description='Get or monitor status of an EVCharge.online site')
    parser.add_argument('search_key', help='A site name, or charge point ID.')
    parser.add_argument('-w', '--watch', action='store_true', help='Keep running, and report changes when observed.')
    parser.add_argument('-p', '--period', type=int, help='Time to wait in seconds between checking status of the site.', default=300)
    parser.add_argument('--store', type=str, help='Location to store the current state.', default='site.json')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='Output file for status updates.', default='-')
    return parser


def coroevent(coro):
    event = asyncio.Event()
    async def wrapper():
        result = await coro
        event.set()
        return result

    async def waiter():
        await event.wait()

    return waiter(), wrapper()


async def async_main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = get_argument_parser()
    args = parser.parse_args(argv)
    store = get_store(args.store)
    output_file = args.output

    notifier = Notifier(output_file)
    async with EVCharge() as evcharge:
        sites = [s async for s in evcharge.search(args.search_key)]
        notification_awaitables = []
        store_awaitables = []
        for site in sites:
            refresh_waiter, refresh_executor = coroevent(site.refresh_points())
            store_awaitables.append(refresh_executor)
            async def notification_awaitable():
                await refresh_waiter
                await notifier.notify_state(site)
            notification_awaitables.append(notification_awaitable())
        
        async def store_awaitable():
            await asyncio.gather(*store_awaitables)
            await store.put_sites(*sites)

        await asyncio.gather(store_awaitable(), *notification_awaitables)

        if args.watch:
            async def notify_current_state():
                for site in sites:
                    await notifier.notify_state(site)

            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGUSR1, lambda: asyncio.create_task(notify_current_state()))
            await asyncio.sleep(args.period)
            await watcher(sites, args.period, store, notifier)


def main(argv=None):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main(argv))


if __name__ == '__main__':
    main()