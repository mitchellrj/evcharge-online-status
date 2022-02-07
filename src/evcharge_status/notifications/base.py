from abc import ABCMeta

from ..models import Site, SiteDiff


class NotifierType(metaclass=ABCMeta):

    async def notify_changes(self, diff: SiteDiff) -> None:
        return NotImplemented

    async def notify_state(self, site: Site) -> None:
        return NotImplemented