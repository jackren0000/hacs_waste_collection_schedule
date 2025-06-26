import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from waste_collection_schedule import Collection  # type: ignore[attr-defined]

TITLE = "Monash City Council"
DESCRIPTION = "Source for Monash City Council rubbish collection."
URL = "https://www.monash.vic.gov.au"
TEST_CASES = {
    "Monash University": {"street_address": "21 Chancellors Walk, Clayton"},
    "Woolworths M-city": {"street_address": "2125 Dandenong Rd, Clayton"},
}

_LOGGER = logging.getLogger(__name__)

ICON_MAP = {
    "Food and Garden Waste": "mdi:leaf",
    "Hard Waste": "mdi:sofa",
    "Recycling": "mdi:recycle",
    "Landfill Waste": "mdi:delete",
}


class Source:
    def __init__(self, street_address):
        self._street_address = street_address

    def fetch(self):
        session = requests.Session()

        # Establish session by loading waste and recycling page
        response = session.get(
            "https://www.monash.vic.gov.au/Waste-Sustainability/Bin-Collection/When-we-collect-your-bins"
        )
        response.raise_for_status()

        # Search for the address
        response = session.get(
            "https://www.monash.vic.gov.au/api/v1/myarea/search",
            params={"keywords": self._street_address},
        )
        response.raise_for_status()
        address_search = response.json()
        if not address_search.get("Items"):
            raise Exception(
                f"Address search for '{self._street_address}' returned no results. "
                f"Check your address on https://www.monash.vic.gov.au/Waste-Sustainability/Bin-Collection/When-we-collect-your-bins"
            )

        top_hit = address_search["Items"][0]
        _LOGGER.debug("Address search top hit: %s", top_hit)

        geolocationid = top_hit["Id"]
        _LOGGER.debug("Geolocation id: %s", geolocationid)

        # Fetch waste services for this location
        response = session.get(
            "https://www.monash.vic.gov.au/ocapi/Public/myarea/wasteservices?ocsvclang=en-AU",
            params={"geolocationid": geolocationid},
        )
        response.raise_for_status()

        waste_result = response.json()
        _LOGGER.debug("Waste API result: %s", waste_result)

        soup = BeautifulSoup(waste_result.get("responseContent", ""), "html.parser")

        entries = []
        for article in soup.find_all("article"):
            waste_type = article.h3.string
            icon = ICON_MAP.get(waste_type)
            next_service = article.find(class_="next-service").string.strip()
            if re.match(r"[^\s]* \d{1,2}/\d{1,2}/\d{4}", next_service):
                date_str = next_service.split(" ")[1]
                service_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                entries.append(Collection(date=service_date, t=waste_type, icon=icon))

        return entries
