from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Preference


@dataclass(frozen=True)
class FlyDestination:
    name: str
    lat: float
    lng: float
    region: str
    airport: str  # arrival airport IATA
    tags: tuple[Preference, ...]
    highlight: str
    day_activities: tuple[tuple[str, str, str, str], ...]
    weekend_extra: tuple[tuple[str, str, str, str], ...] = ()


# Fly-to outdoor destinations across North America (reached by air, then short drive).
FLY_DESTINATIONS: tuple[FlyDestination, ...] = (
    FlyDestination(
        "Zion National Park",
        37.2982,
        -113.0263,
        "Utah",
        "LAS",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "Red sandstone canyons and the famous Narrows.",
        (
            ("09:00", "Zion Canyon Scenic Drive", "1h", "Shuttle through the heart of the canyon."),
            ("10:30", "Riverside Walk to The Narrows", "2h", "Paved path to the river slot canyon."),
            ("14:00", "Emerald Pools Trail", "2h", "Waterfalls and hanging gardens."),
        ),
        (
            ("08:30", "Angels Landing (permit)", "4h", "Iconic chained ridge climb, book a permit."),
        ),
    ),
    FlyDestination(
        "Grand Canyon — South Rim",
        36.0544,
        -112.1401,
        "Arizona",
        "LAS",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "One of the world's great natural wonders.",
        (
            ("09:00", "Mather Point & Rim Trail", "1.5h", "First jaw-dropping canyon views."),
            ("11:00", "Bright Angel Trail (upper)", "2.5h", "Descend a stretch, then climb back."),
            ("15:00", "Hermit Road viewpoints", "2h", "Sunset-worthy overlooks via shuttle."),
        ),
    ),
    FlyDestination(
        "Yellowstone National Park",
        44.428,
        -110.5885,
        "Wyoming",
        "BZN",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Geysers, hot springs, and abundant wildlife.",
        (
            ("09:00", "Old Faithful & Upper Geyser Basin", "2h", "Time your visit to an eruption."),
            ("12:00", "Grand Prismatic Spring", "1.5h", "Overlook trail for the full color."),
            ("15:00", "Grand Canyon of the Yellowstone", "2h", "Lower Falls viewpoints."),
        ),
        (
            ("08:30", "Lamar Valley wildlife drive", "3h", "Bison, wolves, and pronghorn at dawn."),
        ),
    ),
    FlyDestination(
        "Grand Teton National Park",
        43.7904,
        -110.6818,
        "Wyoming",
        "JAC",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "Jagged peaks rising straight from the valley floor.",
        (
            ("09:00", "Jenny Lake & Hidden Falls", "3h", "Boat shuttle plus a waterfall hike."),
            ("13:00", "Taggart Lake Trail", "2h", "Easy loop with reflective peak views."),
        ),
    ),
    FlyDestination(
        "Banff National Park",
        51.4968,
        -115.9281,
        "Alberta, Canada",
        "YYC",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Turquoise lakes framed by the Canadian Rockies.",
        (
            ("09:00", "Lake Louise shoreline", "1.5h", "Iconic glacial lake and tea house trail."),
            ("11:30", "Moraine Lake & Rockpile", "2h", "Valley of the Ten Peaks."),
            ("15:00", "Banff town & gondola", "2h", "Sulphur Mountain summit views."),
        ),
    ),
    FlyDestination(
        "Arches National Park (Moab)",
        38.7331,
        -109.5925,
        "Utah",
        "SLC",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "Over 2,000 natural sandstone arches.",
        (
            ("08:30", "Delicate Arch Trail", "2.5h", "The postcard arch — go early for shade."),
            ("12:00", "Windows Section loop", "1.5h", "Cluster of huge arches, easy walking."),
            ("14:30", "Landscape Arch", "1.5h", "One of the longest arches in the world."),
        ),
    ),
    FlyDestination(
        "Sedona Red Rocks",
        34.8697,
        -111.7609,
        "Arizona",
        "PHX",
        (Preference.HIKING, Preference.CITY_WALK),
        "Red rock buttes, art galleries, and desert trails.",
        (
            ("09:00", "Cathedral Rock Trail", "2h", "Short but steep climb to a saddle view."),
            ("11:30", "Uptown Sedona stroll", "1.5h", "Galleries, cafes, and viewpoints."),
            ("14:00", "Bell Rock Pathway", "1.5h", "Easy trail beneath the famous formation."),
        ),
    ),
    FlyDestination(
        "Rocky Mountain National Park",
        40.3428,
        -105.6836,
        "Colorado",
        "DEN",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Alpine lakes and Trail Ridge Road above the clouds.",
        (
            ("09:00", "Bear Lake & Nymph Lake", "2h", "Accessible alpine lakes loop."),
            ("11:30", "Emerald Lake Trail", "2.5h", "Chain of lakes below sheer peaks."),
            ("15:00", "Trail Ridge Road overlook", "1.5h", "Highest paved road in the US."),
        ),
    ),
    FlyDestination(
        "Joshua Tree National Park",
        33.8734,
        -115.901,
        "California",
        "LAS",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "Surreal desert of twisted trees and boulders.",
        (
            ("09:00", "Hidden Valley Nature Trail", "1h", "Boulder-ringed loop, great intro."),
            ("10:30", "Barker Dam Loop", "1.5h", "Petroglyphs and a desert reservoir."),
            ("13:00", "Keys View", "1h", "Sweeping view over the Coachella Valley."),
        ),
    ),
    FlyDestination(
        "Glacier National Park",
        48.6968,
        -113.7183,
        "Montana",
        "FCA",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Going-to-the-Sun Road and pristine glacial valleys.",
        (
            ("08:30", "Going-to-the-Sun Road", "2.5h", "One of the most scenic drives in America."),
            ("11:30", "Hidden Lake Overlook", "2h", "Alpine trail from Logan Pass."),
            ("15:00", "Lake McDonald shoreline", "1.5h", "Colorful pebbles and calm water."),
        ),
    ),
)
