import os
from typing import Any, Optional, MutableMapping

import aiohttp

from .base import NotifierType
from .const import CONNECTOR_TYPE_NAME, STATE_NAME
from ..const import USER_AGENT
from ..models import ConnectorType, Site, SiteDiff, State


DEFAULT_STATE_STYLE = None
STATE_STYLE = {
    State.AVAILABLE: "primary",
    State.CHARGING: "danger",
    State.OFFLINE: None,
    State.UNKNOWN: DEFAULT_STATE_STYLE,
}


class Notifier(NotifierType):

    session: aiohttp.ClientSession
    channel_id: Optional[str]
    hook_url_or_bearer_token: str
    username: Optional[str]
    icon_emoji: Optional[str]

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(raise_for_status=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    def __init__(self, hook_url_or_bearer_token: str, channel_id: Optional[str]=None, icon_emoji: Optional[str]=None, username: Optional[str]=None):
        self.hook_url_or_bearer_token = hook_url_or_bearer_token
        self.channel_id = channel_id
        self.icon_emoji = f':{icon_emoji}:' if icon_emoji[0] != ':' else icon_emoji
        self.username = username

    async def send(self, message: MutableMapping[str, Any]):
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=utf8",
            "Accept": "application/json",
        }
        if self.hook_url_or_bearer_token.startswith('https://'):
            # it's a hook url
            url = self.hook_url_or_bearer_token
        else:
            headers["Authorization"] = f"Bearer {self.hook_url_or_bearer_token}"
            url = "https://slack.com/api/chat.postMessage"
            if self.channel_id is not None:
                message["channel"] = self.channel_id
            if self.icon_emoji is not None:
                message["icon_emoji"] = self.icon_emoji
            if self.username is not None:
                message["username"] = self.username

        message["unfurl_links"] = False

        async with await self.session.post(
                url,
                headers=headers,
                json=message
            ) as response:

            data = await response.json()
            if not data.get('ok'):
                raise RuntimeError(data['error'])
            return response

    async def notify_changes(self, diff: SiteDiff) -> None:
        if not diff:
            return

        # we only care about changes to points
        if 'points' not in diff.differences:
            return
        
        site: Site = diff.new
        old_site: Site = diff.old
        for guid, point_changes in diff.differences['points'].items():
            point_id = old_site.points.get(guid, site.points.get(guid)).point_id
            if guid not in old_site.points:
                await self.notify(site, f"New charge point, {point_id} added at {site.name}", with_price=True, with_connector_type=True, with_max_power=True)
            if guid not in site.points:
                await self.notify(f"Charge point {point_id} removed from {site.name}")
            for attribute, (old, new) in point_changes.items():
                if attribute == "price":
                    await self.notify(site, f"Price changed for {point_id} at {site.name}", with_price=True)
                elif attribute == "state":
                    old: State
                    new: State
                    old_state_text: str = STATE_NAME.get(old, old.value)
                    new_state_text: str = STATE_NAME.get(new, new.value)
                    await self.notify(site, f"Point {point_id} went from {old_state_text} to {new_state_text}.")
                # Not bothered about anything else


    async def notify_state(self, site: Site):
        heading = f"Current status of charge points at {site.name}"
        return await self.notify(site, heading, with_price=True, with_connector_type=True, with_max_power=True)


    async def notify(self, site: Site, heading, with_price: bool=False, with_connector_type: bool=False, with_max_power: bool=False) -> None:
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": heading
                    }
                }
            ]
        }
        for point in site.points.values():
            connector_text = ""
            price_text = ""
            power_text = ""
            if point.connector_type is not ConnectorType.UNKNOWN and with_connector_type:
                connector_text = f"\n:electric-plug: {CONNECTOR_TYPE_NAME.get(point.connector_type, point.connector_type.value)}"
            if with_price:
                price_text = f"\n:pound: £{point.price}/KWh"
            if with_max_power:
                power_text = f"\n:zap: {point.max_power} KWh"

            message["blocks"].extend([
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{point.point_id}*{connector_text}{power_text}{price_text}"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": STATE_NAME.get(point.state, point.state.value),
                        },
                        "url": f"https://evcharge.online/nologinpoints/{site.guid}",
                    }
                }
            ])
            state_style = STATE_STYLE.get(point.state, DEFAULT_STATE_STYLE)
            if state_style:
                message["blocks"][-1]["accessory"]["style"] = state_style

        await self.send(message)