import datetime
from decimal import Decimal
import json
import re
from typing import Any, Generator, MutableMapping
from urllib.parse import urljoin

import aiohttp
import bs4

from .const import BASE_URL, USER_AGENT
from .models import ConnectorType, Point, Site, State


# very simplistic, does not parse arbitrary args
JS_ARG_PARSER = re.compile(r'\s*\'([^\']+)\'\s*(?:,|\))')
STRIP_WHITESPACE = re.compile(r'(^\s+|\s+$)', re.MULTILINE)


class EVCharge:

    session: aiohttp.ClientSession

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(raise_for_status=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    async def request(self, method: str, path: str, *args: Any, **kwargs: Any) -> aiohttp.ClientResponse:
        url = BASE_URL
        if path:
            url = urljoin(f'{BASE_URL}', path)
        headers = kwargs.pop('headers', {})
        headers.setdefault('User-Agent', USER_AGENT)
        return self.session.request(method, url, headers=headers, *args, **kwargs)

    async def login(self, username: str, password: str):
        form_response = self.request('GET', './login')
        async with await form_response:
            soup = bs4.BeautifulSoup(await form_response.read(), features='html.parser')

        csrf_token_tag = soup.find('input', name='__RequestVerificationToken')
        if not csrf_token_tag:
            raise RuntimeError('Failed to get CSRF token for login')

        csrf_token = csrf_token_tag['value']

        response = self.request('POST', './login', data={
            '__RequestVerificationToken': csrf_token,
            'EmailAddress': username,
            'Password': password,
            'RememberMe': 'false',
            'TimeZone': '0',
            'CurrentLatitude': '',
            'CurrentLongitude': '',
        })
        async with await response:
            await response.read()

    async def search(self, key: str) -> Generator[Site, None, None]:
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

        async with await response:
            data = await response.json()
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

    async def get_site_points(self, guid: str) -> MutableMapping[str, Point]:
        points = {}
        async with await self.request('GET', f'./nologinpoints/{guid}') as response:
            soup = bs4.BeautifulSoup(await response.read(), features='html.parser')

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
            connector_type = ConnectorType.UNKNOWN
            connector_type_tag = point_container.select('.total-energy-icon + span.chrge-left')
            if connector_type_tag:
                connector_type_text = STRIP_WHITESPACE.sub('', connector_type_tag[0].text)
                try:
                    connector_type = ConnectorType(connector_type_text)
                except ValueError:
                    connector_type = ConnectorType.UNKNOWN
            base_url = str(response.url)
            base_tag = soup.find('base')
            if base_tag:
                base_url = base_tag['href']

            image_tag = point_container.select('.chrge-site-img img')
            image_url = None
            if image_tag:
                image_url = urljoin(base_url, image_tag[0]['src'])
            try:
                state = State(state_text)
            except ValueError:
                state = State.UNKNOWN
            points[guid] = Point(guid, point_id, state, price, max_power, connector_type=connector_type, image_url=image_url)

        return points



