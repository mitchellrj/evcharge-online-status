from abc import ABCMeta
from typing import Generator, List

from ..models import Site


class StoreType(metaclass=ABCMeta):

    async def get_sites(self, *site_guids: str) -> Generator[Site, None, None]:
        return NotImplemented

    async def put_sites(self, *sites: Site) -> List[Site]:
        return NotImplemented