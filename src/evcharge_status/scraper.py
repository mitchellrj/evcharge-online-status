import datetime
from decimal import Decimal
import json
import re
from typing import Any, Generator, MutableMapping
from urllib.parse import urljoin

import bs4
import requests

from .const import BASE_URL, USER_AGENT
from .models import Point, Site, State


# very simplistic, does not parse arbitrary args
JS_ARG_PARSER = re.compile(r'\s*\'([^\']+)\'\s*(?:,|\))')
STRIP_WHITESPACE = re.compile(r'(^\s+|\s+$)', re.MULTILINE)


class EVCharge:

    session: requests.Session

    def __init__(self):
        self.session = requests.session()

    def request(self, method: str, path: str, *args: Any, **kwargs: Any) -> requests.Response:
        url = BASE_URL
        if path:
            url = urljoin(f'{BASE_URL}', path)
        headers = kwargs.pop('headers', {})
        headers.setdefault('User-Agent', USER_AGENT)
        response = self.session.request(method, url, headers=headers, *args, **kwargs)
        response.raise_for_status()
        return response

    def search(self, key: str) -> Generator[Site, None, None]:
        response = self.request('POST', './nologinsites', headers={'Content-Type': 'application/json'}, data=json.dumps({
            'CurrentLatitude': '52.06290',
            'CurrentLongitude': '-1.33978',
            'LocalDateTime': datetime.datetime.now().strftime(r'%Y-%m-%d %H:%M:%S'),
            'LocalDateTimeZoneDiff': '0',
            'IsFavourite': '0',
            'ConnectorType': '0',
            'ChargingSpeed': '',
            'PaymentType': '-1',
            'TariffPriceChanged': '0',
            'TariffPriceFrom': '0',
            'TariffPriceTo': '0',
            'PointDistance': '',
            'SearchKey': key
        }))

        data = response.json()
        # return data['MessagePoint'] - this is just a direct link to the GUID of the best matching site

        for site in data.get('objSites', []):
            yield Site(
                site['RefGuid'],
                site['SiteName'],
                site['Address'],
                site['Town'],
                site['County'],
                site['Postcode'],
                site['Country'],
                site['Latitude'],
                site['Longitude'],
                {},
                self,
            )
        return

    def get_site_points(self, guid: str) -> MutableMapping[str, Point]:
        points = {}
        response = self.request('GET', f'./nologinpoints/{guid}')
        soup = bs4.BeautifulSoup(response.content, features='html.parser')
        for point_container in soup.select('.charg-list.site-details'):
            point_row = point_container.find_parent(onclick=True)
            on_click_js = point_row.attrs['onclick']
            # showPointDetails('UKEV1381', '720044004B004A00390072007000760032004F0031007600610054004800480031004E00540034004E0051003D003D00', '22', '0.1800', '1', 'False' )
            # point, guid, kwh deliverable, cost, bill type, is vrm r
            on_click_args = JS_ARG_PARSER.findall(on_click_js)
            point_id = on_click_args[0]
            guid = on_click_args[1]
            max_power = float(on_click_args[2])
            price = Decimal(on_click_args[3].rstrip('0'))
            state_text = STRIP_WHITESPACE.sub('', point_container.select('button')[0].text)
            try:
                state = State(state_text)
            except ValueError:
                state = State.UNKNOWN
            points[guid] = Point(guid, point_id, state, price, max_power, None)

        return points



