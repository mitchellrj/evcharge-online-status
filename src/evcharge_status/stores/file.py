import json
from typing import Any, Generator, List, Mapping, Union

from ..models import Point, Site, State


JSONType = Union[bool, float, int, List['JSONType'], Mapping[str, 'JSONType'], None, str]


class Store:

    def __init__(self, file_path: str):
        self.file_path = file_path
        # create the file if it doesn't exist
        with open(self.file_path, 'a+') as fh:
            if fh.tell() == 0:
                # if the file is empty
                fh.write(json.dumps({}))

    @classmethod
    def format_point(self, point: Point) -> JSONType:
        return {
            "point_id": point.point_id,
            "state": point.state.value,
            "price": str(point.price),
            "max_power": point.max_power,
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
            points.append(Point(
                guid,
                point.get("point_id"),
                state,
                point.get("price"),
                point.get("max_power"),
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

    def get_sites(self, *site_guids: str) -> Generator[Site, None, None]:
        with open(self.file_path, 'r') as fh:
            data = json.loads(fh)

        for site in data:
            yield self.parse_site(site)
    
    def put_sites(self, *sites: Site) -> List[Site]:
        sites_data = {
            site.guid: self.format_site(site)
            for site in sites
        }
        with open(self.file_path, 'r+') as fh:
            fh.seek(0)
            existing_data = json.loads(fh.read())
            fh.seek(0)
            fh.truncate(0)
            existing_data.update(sites_data)
            fh.write(json.dumps(existing_data))

        return sites