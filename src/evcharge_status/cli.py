import argparse
import asyncio
import os
import signal
import sys
import threading

from evcharge_status.notifications.file import Notifier as FileNotifier
from evcharge_status.notifications.multi import Notifier as MultiNotifier
from evcharge_status.notifications.slack import Notifier as SlackNotifier
from evcharge_status.scraper import EVCharge
from evcharge_status.stores import get_store
from evcharge_status.watcher import Watcher


def get_argument_parser():
    parser = argparse.ArgumentParser(description='Get or monitor status of an EVCharge.online site')
    parser.add_argument(
        'search_key',
        help='A site name, or charge point ID.',
        default=os.getenv("EVCHARGE_SEARCH_KEY")
        )
    parser.add_argument(
        '-w', '--watch',
        action='store_true',
        help='Keep running, and report changes when observed.',
        default=(
            os.getenv("EVCHARGE_WATCH", "").lower()
            in ('yes', '1', 'true', 'y', 'on')
        ))
    parser.add_argument(
        '-p', '--period',
        type=int,
        help='Time to wait in seconds between checking status of the site.',
        default=int(os.getenv('EVCHARGE_WATCH_PERIOD', 300))
        )
    parser.add_argument(
        '--store',
        help='Location to store the current state.',
        default=os.getenv("EVCHARGE_STORE", 'site.json')
        )
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        help='Output file for status updates.',
        default=os.getenv("EVCHARGE_OUTPUT", '-')
        )
    parser.add_argument(
        '-q', '--quiet',
        action="store_true",
        help="Don't output current status when starting, only output changes.",
        default=(
            os.getenv("EVCHARGE_QUIET", "").lower()
            in ('yes', '1', 'true', 'y', 'on')
        ))
    
    slack_group = parser.add_argument_group('Slack options')
    slack_group.add_argument(
        '--slack-hook-url',
        help="Hook URL for Slack.",
        default=os.getenv('SLACK_HOOK_URL')
        )
    slack_group.add_argument(
        '--slack-token',
        help="Bot or user token for Slack.",
        default=os.getenv('SLACK_TOKEN')
        )
    slack_group.add_argument(
        '--slack-channel-id',
        help="Channel ID of the Slack channel to post updates to.",
        default=os.getenv('SLACK_CHANNEL_ID"')
        )
    slack_group.add_argument(
        '--slack-icon-emoji',
        help='Emoji to use as the icon for the Slack bot messages.',
        default=os.getenv('SLACK_ICON_EMOJI')
        )
    slack_group.add_argument(
        '--slack-username',
        help='Username for the Slack bot messages.',
        default=os.getenv('SLACK_USERNAME')
        )
    return parser


def parse_args(argv):
    parser = get_argument_parser()
    args = parser.parse_args(argv)
    if args.slack_channel_id and args.slack_hook_url:
        parser.error("--slack-channel-id cannot be specified with --slack-hook-url")
    if args.slack_icon_emoji and args.slack_hook_url:
        parser.error("--slack-icon-emoji cannot be specified with --slack-hook-url")
    if args.slack_username and args.slack_hook_url:
        parser.error("--slack-username cannot be specified with --slack-hook-url")
    return args


def multiwait(coro):
    """Take a coroutine and return a tuple of two coroutines, both of which
    will resolve at the same time. The second of which invokes the original
    coroutine when awaited.

    Used to order events when two independent events depend on the same event.
    """

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

    args = parse_args(argv)
    store = get_store(args.store)
    output_file = args.output

    slack_secret = args.slack_hook_url or args.slack_token
    notifier = FileNotifier(output_file)
    if slack_secret:
        notifier = MultiNotifier([
            notifier,
            SlackNotifier(slack_secret, args.slack_channel_id, args.slack_icon_emoji, args.slack_username)
        ])
    async with notifier:
        async with EVCharge() as evcharge:
            sites = [s async for s in evcharge.search(args.search_key)]
            notification_awaitables = []
            store_awaitables = []
            for site in sites:
                refresh_waiter, refresh_executor = multiwait(site.refresh_points())
                store_awaitables.append(refresh_executor)
                async def notification_awaitable():
                    await refresh_waiter
                    if not args.quiet:
                        await notifier.notify_state(site)
                notification_awaitables.append(notification_awaitable())
            
            async def store_awaitable():
                await asyncio.gather(*store_awaitables)
                await store.put_sites(*sites)

            await asyncio.gather(store_awaitable(), *notification_awaitables)

            if args.watch:

                loop = asyncio.get_running_loop()
                async def notify_current_state():
                    notification_awaitables = []
                    for site in sites:
                        notification_awaitables.append(notifier.notify_state(site))

                    await asyncio.gather(*notification_awaitables)

                if 'win' not in sys.platform:
                    add_signal_handler = loop.add_signal_handler
                    # add listener for SIGUSR1 if available
                    add_signal_handler(signal.SIGUSR1, lambda *_: asyncio.create_task(notify_current_state()))
                else:
                    add_signal_handler = signal.signal

                def stop_on_signal(sig, *args):
                    watcher.stop()

                watcher = Watcher(sites, args.period, store, notifier)
                add_signal_handler(signal.SIGINT, stop_on_signal)

                async with watcher:
                    await watcher.run()


def main(argv=None):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main(argv))


if __name__ == '__main__':
    main()