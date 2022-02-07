import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import time
from typing import Any, Generator, List, Mapping, MutableMapping

import boto3

from .base import StoreType
from ..models import ConnectorType, Point, Site, State, Union

# Design note:
# Using conditional writes charges you for a write even if it doesn't result in an update,
# so we do a separate read and then decide whether we want to write back or not. Conditional
# writes are useful for isolation, but not efficiency.
#
# Schema:
#
# site_guid: S (PK)
# name: S
# address: S
# town: S
# county: S
# postcode: S
# country: S
# lat: S
# lng: S
# points: M {
#   point_guid: {
#     point_id: S
#     state: S
#     price: S
#     max_power: N
#     connector_type: S
#     image_url: S
#   }
# }
# last_checked: N

DynamoDBItem = Mapping[str, Mapping[str, Union[bool, float, int, List['DynamoDBItem'], Mapping[str, 'DynamoDBItem'], None, str]]]


class Field:
    
    SITE_GUID = 'site_guid'
    SITE_NAME = 'name'
    SITE_ADDRESS = 'address'
    SITE_TOWN = 'town'
    SITE_COUNTY = 'county'
    SITE_POSTCODE = 'postcode'
    SITE_COUNTRY = 'country'
    SITE_LAT = 'lat'
    SITE_LNG = 'lng'
    SITE_POINTS = 'points'
    SITE_CHECKED = 'last_checked'
    POINT_ID = 'point_id'
    POINT_STATE = 'state'
    POINT_PRICE = 'price'
    POINT_MAX_POWER = 'max_power'
    POINT_CONNECTOR_TYPE = 'connector_type'
    POINT_IMAGE_URL = 'image_url'


class Store(StoreType):

    table_name: str

    def __init__(self, table_name: str):
        self.client = boto3.client('dynamodb')
        self.table_name = table_name

    @classmethod
    def parse_site(cls, item: DynamoDBItem) -> Site:
        points = {}
        for point_guid, point_data in item.get(Field.SITE_POINTS, {}).get('M', {}).items():
            # shouldn't need to account for bad state values in the table, but just in case
            state_text = point_data.get(Field.POINT_STATE, {}).get('S')
            try:
                state = State(state_text)
            except ValueError:
                state = State.UNKNOWN
            # shouldn't need to account for bad state values in the table, but just in case
            connector_type_text = point_data.get(Field.POINT_CONNECTOR_TYPE, {}).get('S')
            try:
                connector_type = ConnectorType(connector_type_text)
            except ValueError:
                connector_type = ConnectorType.UNKNOWN
            points[point_guid] = Point(
                point_data.get(Field.POINT_ID, {}).get('S'),
                state,
                Decimal(point_data.get(Field.POINT_PRICE, {}).get('S', '0')),
                point_data.get(Field.POINT_MAX_POWER, {}).get('N', 0),
                connector_type,
                point_data.get(Field.POINT_IMAGE_URL, {}).get('S', None)
            )
        return Site(
            item[Field.SITE_GUID]['S'],
            item.get(Field.SITE_NAME, {}).get('S'),
            item.get(Field.SITE_ADDRESS, {}).get('S'),
            item.get(Field.SITE_TOWN, {}).get('S'),
            item.get(Field.SITE_COUNTY, {}).get('S'),
            item.get(Field.SITE_POSTCODE, {}).get('S'),
            item.get(Field.SITE_COUNTRY, {}).get('S'),
            item.get(Field.SITE_LAT, {}).get('S'),
            item.get(Field.SITE_LNG, {}).get('S'),
            points
        )

    @classmethod
    def format_point(self, point: Point) -> DynamoDBItem:
        return {
            Field.POINT_ID: {
                'S': point.point_id
            },
            Field.POINT_STATE: {
                'S': point.state.value
            },
            Field.POINT_PRICE: {
                'S': str(point.price)
            },
            Field.POINT_MAX_POWER: {
                'N': point.max_power
            },
            Field.POINT_CONNECTOR_TYPE: {
                'S': point.connector_type.value
            },
            Field.POINT_IMAGE_URL: {
                'S': point.image_url
            }
        }

    @classmethod
    def format_site(self, site: Site) -> DynamoDBItem:
        points_data: MutableMapping[str, DynamoDBItem] = {
            point.guid: self.format_point(point)
            for point in site.points
        }
        return {
            Field.SITE_GUID: {
                'S': site.guid
            },
            Field.SITE_NAME: {
                'S': site.name
            },
            Field.SITE_ADDRESS: {
                'S': site.address
            },
            Field.SITE_TOWN: {
                'S': site.town
            },
            Field.SITE_COUNTY: {
                'S': site.county
            },
            Field.SITE_POSTCODE: {
                'S': site.postcode
            },
            Field.SITE_COUNTRY: {
                'S': site.country
            },
            Field.SITE_LAT: {
                'S': site.lat
            },
            Field.SITE_LNG: {
                'S': site.lng
            },
            Field.SITE_POINTS: {
                'M': points_data
            },
            Field.SITE_CHECKED: {
                'N': time.time()
            }
        }

    def _get_sites(self, *site_guids: str) -> Generator[Site, None, None]:
        unprocessed_keys = [
            {
                Field.SITE_GUID: {
                    'S': site_guid
                }
            } for site_guid in site_guids
        ]
        while unprocessed_keys:
            response = self.client.batch_get_item(
                RequestItems={
                    self.table_name: {
                        'Keys': unprocessed_keys
                    }
                }
            )
            for result in response['Responses'][self.table_name]:
                yield self.parse_site(result)

            unprocessed_keys = result['UnprocessedKeys'][self.table_name]['Keys']

    async def get_sites(self, *site_guids: str) -> Generator[Site, None, None]:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(self._get_sites(*site_guids))
            async for site in asyncio.wrap_future(future):
                yield site

    def _put_sites(self, *sites: Site) -> List[Site]:
        results = []
        unprocessed_items = [
            {
                'PutRequest': {
                    'Item': self.format_site(site)
                }
            } for site in sites
        ]
        while unprocessed_items:
            response = self.client.batch_put_item(
                RequestItems={
                    self.table_name: unprocessed_items
                }
            )
            for result in response['Responses'][self.table_name]:
                # don't use a generator, otherwise if the results aren't read, any remaining
                # unprocessed items won't be processed
                results.append(self.parse_site(result))

            unprocessed_items = result['UnprocessedItems'][self.table_name]

        return results

    async def put_sites(self, *sites: Site) -> List[Site]:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(self._put_sites(*sites))
            await asyncio.wrap_future(future)