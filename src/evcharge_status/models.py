from decimal import Decimal
import enum
from re import S
from typing import Any, List, MutableMapping, NamedTuple, Optional, Set, Tuple


class ConnectorType(enum.IntEnum):

    UK_3_PIN = 1
    CCS = 2
    CHADEMO = 3
    TYPE_1 = 4
    TYPE_2 = 5

class State(enum.Enum):

    AVAILABLE = 'AVAILABLE'
    CHARGING  = 'CHARGING'
    UNKNOWN   = 'UNKNOWN'


class Point:
    guid: str
    point_id: str
    state: State
    price: Decimal
    max_power: float
    connector_type: Optional[ConnectorType]

    def __init__(self, guid: str, point_id: str, state: State, price: Decimal,
            max_power: float, connector_type: Optional[ConnectorType]=None):
        self.guid = guid
        self.point_id = point_id
        self.state = state
        self.price = price
        self.max_power = max_power
        self.connector_type = connector_type


class Site:
    
    guid: str
    name: Optional[str]
    address: Optional[str]
    town: Optional[str]
    county: Optional[str]
    postcode: Optional[str]
    country: Optional[str]
    lat: Optional[str]
    lng: Optional[str]

    def __init__(
            self, guid: str, name: Optional[str]=None, address: Optional[str]=None,
            town: Optional[str]=None, county: Optional[str]=None, postcode: Optional[str]=None,
            country: Optional[str]=None, lat: Optional[str]=None, lng: Optional[str]=None,
            points: Optional[List[Point]]=None, evcharge: Any=None):
        self.guid = guid
        self.name = name
        self.address = address
        self.town = town
        self.county = county
        self.postcode = postcode
        self.country = country
        self.lat = lat
        self.lng = lng
        self._points = points
        self.__evcharge = evcharge

    @property
    def _evcharge(self):
        if self.__evcharge is None:
            from . import scraper
            self.__evcharge = scraper.EVCharge()

        return self.__evcharge

    @property
    def points(self) -> List[Point]:
        if self._points is None:
            self.refresh_points()
        
        return self._points
    
    async def refresh_points(self) -> None:
        self._points = await self._evcharge.get_site_points(self.guid)

    def __str__(self) -> str:
        return self.guid

    def __eq__(self, other) -> bool:
        return self.guid == other.guid

    def copy(self) -> 'Site':
        return Site(
            self.guid,
            self.name,
            self.address,
            self.town,
            self.county,
            self.postcode,
            self.country,
            self.lat,
            self.lng,
            self.points,
            self._evcharge
        )


class SiteDiff:

    guid: str
    old: Site
    new: Site

    def __init__(self, old, new, differences: MutableMapping[str, Tuple[Any, Any]]):
        self.guid = old.guid
        self.old = old
        self.new = new
        self.__differences = differences

    @property
    def differences(self) -> MutableMapping[str, Tuple[Any, Any]]:
        return dict(self.__differences.items())

    def __bool__(self):
        return len(self.differences) > 0

    @classmethod
    def from_sites(cls, old_site: Site, new_site: Site):
        assert old_site.guid == new_site.guid
        changed: MutableMapping[str, Tuple[Any, Any]] = {}

        for attr in ('name', 'address', 'town', 'county', 'postcode', 'country', 'lat', 'lng'):
            old = getattr(old_site, attr, None)
            new = getattr(new_site, attr, None)
            if old != new:
                changed[attr] = (old, new)

        old_points: Set[str] = set(old_site.points.keys())
        new_points: Set[str] = set(new_site.points.keys())

        points_changed: MutableMapping[str, MutableMapping[str, Tuple[Any, Any]]] = {}

        for guid in (old_points | new_points):
            point_diff = {}
            for attr in ('price', 'connector_type', 'point_id', 'state', 'max_power'):
                old = getattr(old_site.points.get(guid, None), attr, None)
                new = getattr(new_site.points.get(guid, None), attr, None)
                if old != new:
                    point_diff[attr] = (old, new)
            
            if point_diff:
                points_changed[guid] = point_diff

        changed['points'] = points_changed

        return cls(old_site, new_site, changed)