import os
from typing import Optional, TextIO, Union
import sys

import aiofiles

from .const import CONNECTOR_TYPE_NAME, STATE_NAME
from ..const import DEFAULT_ENCODING
from ..models import Site, SiteDiff

class Notifier:

    def __init__(self, file_path_or_writable: Optional[Union[str, TextIO]]=None, encoding: Optional[str]=None):
        if file_path_or_writable is None:
            file_path_or_writable = sys.stdout
        self.file_path_or_writable = file_path_or_writable
        if encoding is None:
            encoding = DEFAULT_ENCODING
        self.encoding = encoding

    async def write(self, message: str) -> int:
        message = f'{message}{os.linesep}'
        if isinstance(self.file_path_or_writable, str):
            async with aiofiles.open(self.file_path_or_writable, 'a+', encoding=self.encoding) as fh:
                return await fh.write(message)
        else:
            return self.file_path_or_writable.write(message)

    async def notify_changes(self, diff: SiteDiff) -> None:
        if not diff:
            return

        # any changes to site metadata?
        if len(diff.differences) > 1 or 'points' not in diff.differences:
            for attribute, (old, new) in diff.differences.items():
                if attribute == 'points':
                    continue
                await self.write(f'{diff.old.name}: {attribute} changed from {str(old)} to {str(new)}')

        if 'points' in diff.differences:
            for guid, point_changes in diff.differences['points'].items():
                point_id = diff.old.points.get(guid, diff.new.points.get(guid)).point_id
                for attribute, (old, new) in point_changes.items():
                    await self.write(f'{point_id}: {attribute} changed from {str(old)} to {str(new)}')

    async def notify_state(self, site: Site) -> None:
        await self.write(f'* {site.name}:')
        await self.write(f'  {site.address}')
        await self.write(f'  {site.town}')
        await self.write(f'  {site.county}')
        await self.write(f'  {site.postcode}')
        await self.write(f'  {site.country}')
        await self.write(f'  ({site.lat}, {site.lng})')
        for point in site.points.values():
            await self.write(f'  - {point.point_id}')
            await self.write(f'    {STATE_NAME.get(point.state, point.state.value)}')
            if point.connector_type is not None:
                await self.write(f'    Connector: {CONNECTOR_TYPE_NAME.get(point.connector_type, point.connector_type.value)}')
            await self.write(f'    {point.max_power} KWh')
            await self.write(f'    £{point.price}/KWh')