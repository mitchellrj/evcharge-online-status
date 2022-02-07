import json
import time
from typing import Any, Generator, List, Mapping, Union

import aiofiles

from .base import StoreType
from ..models import ConnectorType, Point, Site, State


JSONType = Union[bool, float, int, List['JSONType'], Mapping[str, 'JSONType'], None, str]


class Store(StoreType):

    def __init__(self, file_path: str):
        self.file_path = file_path

    @classmethod
    def format_point(self, point: Point) -> JSONType:
        return {
            "point_id": point.point_id,
            "state": point.state.value,
            "price": str(point.price),
            "max_power": point.max_power,
            "connector_type": point.connector_type.value,
            "image_url": point.image_url,
        }

    @classmethod
    def format_site(self, site: Site) -> JSONType:
        return {
            "guid": site.guid,
            "name": site.name,
            "address": site.address,
            "town": site.town,
            "county": site.county,
            "postcode": site.postcode,
            "country": site.country,
            "lat": site.lat,
            "lng": site.lng,
            "points": {guid: self.format_point(point) for guid, point in site.points.items()},
            "last_checked": time.time()
        }

    @classmethod
    def parse_site(self, site: JSONType) -> Site:
        points = {}
        for guid, point in site.get('points', []).items():
            state_text = point.get("state")
            try:
                state = State(state_text)
            except ValueError:
                state = State.UNKNOWN
            connector_type_text = point.get("connector_type")
            try:
                connector_type = ConnectorType(connector_type_text)
            except ValueError:
                connector_type = ConnectorType.UNKNOWN
            points.append(Point(
                guid,
                point.get("point_id"),
                state,
                point.get("price"),
                point.get("max_power"),
                connector_type,
                point.get("image_url"),
            ))
        return Site(
            site.get('guid'),
            site.get('name'),
            site.get('address'),
            site.get('town'),
            site.get('county'),
            site.get('postcode'),
            site.get('country'),
            site.get('lat'),
            site.get('lng'),
            points,
        )

    async def _init_store(self):
        # create the file if it doesn't exist
        async with aiofiles.open(self.file_path, 'a+') as fh:
            if await fh.tell() == 0:
                # if the file is empty
                await fh.write(json.dumps({}))

    async def get_sites(self, *site_guids: str) -> Generator[Site, None, None]:
        await self._init_store()
        async with aiofiles.open(self.file_path, 'r') as fh:
            data = json.loads(await fh.read())

        async for site in data:
            yield self.parse_site(site)
    
    async def put_sites(self, *sites: Site) -> List[Site]:
        sites_data = {
            site.guid: self.format_site(site)
            for site in sites
        }
        await self._init_store()
        async with aiofiles.open(self.file_path, 'r+') as fh:
            await fh.seek(0)
            existing_data = json.loads(await fh.read())
            await fh.seek(0)
            await fh.truncate(0)
            existing_data.update(sites_data)
            await fh.write(json.dumps(existing_data))

        return sites