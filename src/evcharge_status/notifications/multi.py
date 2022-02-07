import asyncio
from typing import Sequence

from .base import NotifierType
from ..models import Site, SiteDiff

class Notifier(NotifierType):

    notifiers: Sequence[NotifierType]

    def __init__(self, notifiers: Sequence[NotifierType]):
        self.notifiers = notifiers

    async def __aenter__(self):
        for notifier in self.notifiers:
            await notifier.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        for notifier in self.notifiers:
            await notifier.__aexit__(exc_type, exc, tb)

    async def notify_changes(self, diff: SiteDiff) -> None:
        await asyncio.gather(*[
            notifier.notify_changes(diff) for notifier in self.notifiers
        ])

    async def notify_state(self, site: Site) -> None:
        await asyncio.gather(*[
            notifier.notify_state(site) for notifier in self.notifiers
        ])