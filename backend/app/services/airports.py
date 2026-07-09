from __future__ import annotations

from dataclasses import dataclass

from app.services.geo import haversine_miles


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    lat: float
    lng: float


# Major US/Canada airports used to resolve a traveler's nearest origin airport.
AIRPORTS: tuple[Airport, ...] = (
    Airport("SFO", "San Francisco Intl", 37.6213, -122.379),
    Airport("OAK", "Oakland Intl", 37.7126, -122.2197),
    Airport("SJC", "San Jose Intl", 37.3639, -121.9289),
    Airport("LAX", "Los Angeles Intl", 33.9416, -118.4085),
    Airport("SAN", "San Diego Intl", 32.7338, -117.1933),
    Airport("SMF", "Sacramento Intl", 38.6954, -121.5908),
    Airport("SEA", "Seattle-Tacoma Intl", 47.4502, -122.3088),
    Airport("PDX", "Portland Intl", 45.5898, -122.5951),
    Airport("LAS", "Harry Reid Intl (Las Vegas)", 36.084, -115.1537),
    Airport("PHX", "Phoenix Sky Harbor", 33.4342, -112.0116),
    Airport("SLC", "Salt Lake City Intl", 40.7899, -111.9791),
    Airport("DEN", "Denver Intl", 39.8561, -104.6737),
    Airport("BZN", "Bozeman Yellowstone Intl", 45.7772, -111.1602),
    Airport("JAC", "Jackson Hole", 43.6073, -110.7377),
    Airport("FCA", "Glacier Park Intl", 48.3105, -114.256),
    Airport("YYC", "Calgary Intl", 51.1315, -114.0106),
    Airport("ANC", "Ted Stevens Anchorage Intl", 61.1743, -149.9962),
    Airport("FAI", "Fairbanks Intl", 64.8151, -147.856),
    Airport("YZF", "Yellowknife", 62.4628, -114.4403),
    Airport("YXY", "Erik Nielsen Whitehorse Intl", 60.7096, -135.0674),
    Airport("ORD", "Chicago O'Hare", 41.9742, -87.9073),
    Airport("DFW", "Dallas/Fort Worth", 32.8998, -97.0403),
    Airport("JFK", "New York JFK", 40.6413, -73.7781),
    Airport("BOS", "Boston Logan", 42.3656, -71.0096),
    Airport("ATL", "Atlanta Hartsfield-Jackson", 33.6407, -84.4277),
    Airport("MIA", "Miami Intl", 25.7959, -80.287),
)

_BY_IATA = {a.iata: a for a in AIRPORTS}


def airport_by_iata(iata: str) -> Airport | None:
    return _BY_IATA.get(iata.upper())


def nearest_airport(lat: float, lng: float) -> Airport:
    return min(AIRPORTS, key=lambda a: haversine_miles(lat, lng, a.lat, a.lng))
