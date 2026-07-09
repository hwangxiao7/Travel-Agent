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
        "Catalina Island — Avalon",
        33.3422,
        -118.3287,
        "California",
        "LAX",
        (Preference.BEACH, Preference.CITY_WALK),
        "Island day trip for snorkeling, glass-bottom boats, and Avalon town walks.",
        (
            ("09:30", "Lover's Cove snorkeling", "2.5h", "Clear water snorkeling with fish and kelp near Avalon."),
            ("13:00", "Avalon waterfront stroll", "2h", "City-walk cafes, shops, and harbor views."),
            ("15:30", "Glass-bottom boat (optional)", "1h", "See the reef without getting wet."),
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
    # High-latitude aurora destinations (fly trips; not Bay Area day drives).
    FlyDestination(
        "Fairbanks — Northern Lights",
        64.8378,
        -147.7164,
        "Alaska",
        "FAI",
        (Preference.HIKING, Preference.FOREST),
        "One of the world's most reliable aurora cities under the auroral oval.",
        (
            ("10:00", "Museum of the North", "1.5h", "Alaska culture and aurora science exhibits."),
            ("13:00", "Chena Hot Springs day trip", "4h", "Soak outdoors while waiting for clear skies."),
            ("21:30", "Aurora viewing (Cleary Summit / Murphy Dome)", "3h", "Dark-sky ridges north of town for northern lights."),
        ),
        (
            ("22:00", "Guided aurora tour / cabin night", "4h", "Remote dark-sky site with heated shelter."),
        ),
    ),
    FlyDestination(
        "Denali National Park",
        63.1148,
        -151.1926,
        "Alaska",
        "FAI",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Alaska's flagship park — alpine tundra by day, aurora by night in winter.",
        (
            ("09:00", "Denali Visitor Center & park road views", "2h", "Orientation and mountain vistas when weather allows."),
            ("12:00", "Easy tundra / riverside walk near entrance", "2h", "Wildlife spotting without a long shuttle."),
            ("21:00", "Aurora watch near Healy / park boundary", "3h", "High-latitude northern lights away from city glow."),
        ),
        (
            ("08:30", "Savage River loop", "2.5h", "Classic day hike with Denali views on clear days."),
        ),
    ),
    FlyDestination(
        "Yellowknife — Aurora Capital",
        62.4540,
        -114.3718,
        "Northwest Territories, Canada",
        "YZF",
        (Preference.CITY_WALK, Preference.HIKING),
        "Canada's aurora capital on the edge of Great Slave Lake.",
        (
            ("11:00", "Old Town & Pilot's Monument", "1.5h", "Colorful houseboats and lake overlooks."),
            ("14:00", "Frame Lake Trail", "1.5h", "Easy urban nature walk."),
            ("22:00", "Aurora village / Prosperous Lake viewing", "4h", "Guided northern-lights night under dark skies."),
        ),
        (
            ("21:30", "Glass-walled aurora lodge night", "5h", "Warm viewing cabin while waiting for the lights."),
        ),
    ),
    FlyDestination(
        "Whitehorse & Yukon aurora",
        60.7212,
        -135.0568,
        "Yukon, Canada",
        "YXY",
        (Preference.HIKING, Preference.FOREST),
        "Yukon wilderness gateway with strong winter aurora odds.",
        (
            ("10:00", "Miles Canyon walk", "1.5h", "Basalt canyon on the Yukon River."),
            ("13:00", "SS Klondike / waterfront", "1h", "Town history and river views."),
            ("21:30", "Aurora viewing outside city lights", "3h", "Northern lights over boreal forest."),
        ),
    ),
)
