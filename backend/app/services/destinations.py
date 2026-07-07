from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Preference


@dataclass(frozen=True)
class Destination:
    name: str
    lat: float
    lng: float
    region: str
    tags: tuple[Preference, ...]
    highlight: str
    day_activities: tuple[tuple[str, str, str, str], ...]
    weekend_extra: tuple[tuple[str, str, str, str], ...] = ()


# Curated NA destinations for MVP (works without external POI APIs)
DESTINATIONS: tuple[Destination, ...] = (
    Destination(
        "Yosemite National Park",
        37.8651,
        -119.5383,
        "California",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Granite cliffs, waterfalls, and iconic valley views.",
        (
            ("09:00", "Tunnel View", "45min", "Classic panorama of El Capitan and Half Dome."),
            ("10:30", "Lower Yosemite Fall Trail", "1.5h", "Easy paved walk to the base of the falls."),
            ("13:00", "Valley picnic / Curry Village", "1h", "Grab lunch before the afternoon hike."),
            ("14:30", "Mirror Lake Loop", "1.5h", "Flat loop with reflective views of Half Dome."),
        ),
        (
            ("08:30", "Glacier Point Road lookout", "2h", "Sweeping high-elevation views (seasonal access)."),
            ("11:30", "Mariposa Grove", "2h", "Giant sequoias and quiet forest trails."),
        ),
    ),
    Destination(
        "Muir Woods National Monument",
        37.8955,
        -122.5814,
        "California",
        (Preference.FOREST, Preference.HIKING),
        "Coastal redwoods minutes from the Bay Area.",
        (
            ("09:30", "Main Trail loop", "1.5h", "Boardwalk among old-growth redwoods."),
            ("11:30", "Hillside Trail extension", "1h", "Quieter upland loop with filtered light."),
            ("13:00", "Mill Valley lunch", "1h", "Head back toward town for food."),
        ),
    ),
    Destination(
        "Point Reyes National Seashore",
        38.0444,
        -122.8029,
        "California",
        (Preference.HIKING, Preference.BEACH),
        "Dramatic coastline, tule elk, and lighthouse views.",
        (
            ("09:00", "Tomales Point Trail", "2h", "Coastal bluffs with elk sightings."),
            ("12:00", "Drakes Beach", "1h", "Wide sandy beach and picnic spot."),
            ("14:00", "Point Reyes Lighthouse", "1.5h", "Steep steps down to the cliffside beacon."),
        ),
    ),
    Destination(
        "Big Basin Redwoods State Park",
        37.1722,
        -122.2219,
        "California",
        (Preference.FOREST, Preference.HIKING),
        "Shaded redwood groves south of San Francisco.",
        (
            ("09:30", "Redwood Loop Trail", "1.5h", "Gentle intro to the park's tallest trees."),
            ("11:30", "Sempervirens Falls", "2h", "Moderate waterfall hike through fern canyon."),
        ),
    ),
    Destination(
        "Golden Gate Park & Lands End",
        37.7694,
        -122.4862,
        "San Francisco",
        (Preference.CITY_WALK, Preference.BEACH),
        "Urban oasis plus rugged Pacific cliff walk.",
        (
            ("10:00", "Japanese Tea Garden", "1h", "Calm start in the heart of the park."),
            ("11:30", "Conservatory of Flowers", "45min", "Victorian greenhouse and gardens."),
            ("13:00", "Lands End Trail", "2h", "Coastal walk with Golden Gate views."),
        ),
    ),
    Destination(
        "Lake Tahoe — Emerald Bay",
        38.9382,
        -120.1143,
        "California/Nevada",
        (Preference.HIKING, Preference.BEACH, Preference.FOREST),
        "Alpine lake with crystal water and pine forests.",
        (
            ("09:00", "Emerald Bay Lookout", "45min", "Photo stop above the bay."),
            ("10:30", "Vikingsholm / Eagle Falls", "2h", "Shoreline trail and short waterfall hike."),
            ("14:00", "Sand Harbor beach time", "1.5h", "Clear shallow water and smooth boulders."),
        ),
    ),
    Destination(
        "Mount Tamalpais State Park",
        37.9235,
        -122.5965,
        "California",
        (Preference.HIKING, Preference.FOREST),
        "Bay views above fog and redwood canyons.",
        (
            ("09:00", "East Peak fire lookout", "1h", "360° views on clear days."),
            ("10:30", "Dipsea / Steep Ravine loop", "2.5h", "Classic Marin hike with stairs and creeks."),
        ),
    ),
    Destination(
        "Pinnacles National Park",
        36.4906,
        -121.1825,
        "California",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "Volcanic spires, talus caves, and condor country.",
        (
            ("09:00", "Bear Gulch Cave Trail", "2h", "Cave passage and reservoir views."),
            ("12:00", "High Peaks Trail section", "2h", "Rocky ridgeline with iron handholds."),
        ),
    ),
    Destination(
        "Portland — Forest Park & Pearl District",
        45.5231,
        -122.6765,
        "Oregon",
        (Preference.CITY_WALK, Preference.FOREST),
        "Urban forest trails plus walkable neighborhoods.",
        (
            ("10:00", "Wildwood Trail (Lower Macleay)", "2h", "Forest in the city with creek views."),
            ("13:00", "Pearl District stroll", "2h", "Coffee, bookstores, and riverfront walk."),
        ),
    ),
    Destination(
        "Columbia River Gorge — Multnomah Falls",
        45.5762,
        -122.1158,
        "Oregon",
        (Preference.HIKING, Preference.FOREST),
        "Waterfalls and gorge viewpoints east of Portland.",
        (
            ("09:30", "Multnomah Falls", "1h", "Iconic two-tier falls and Benson Bridge."),
            ("11:00", "Wahkeena Loop", "2.5h", "Lush forest with multiple smaller falls."),
        ),
    ),
    Destination(
        "Olympic National Park — Hurricane Ridge",
        47.9708,
        -123.4983,
        "Washington",
        (Preference.NATIONAL_PARK, Preference.HIKING, Preference.FOREST),
        "Alpine meadows and mountain vistas near Seattle.",
        (
            ("09:00", "Hurricane Ridge Visitor Center", "45min", "Orientation and ridge views."),
            ("10:30", "Hurricane Hill Trail", "2h", "Paved climb to panoramic summit."),
            ("14:00", "Lake Crescent shoreline", "1.5h", "Clear glacial lake stop on the drive."),
        ),
    ),
    Destination(
        "Mount Rainier — Paradise",
        46.7867,
        -121.7354,
        "Washington",
        (Preference.NATIONAL_PARK, Preference.HIKING),
        "Wildflower meadows beneath an active volcano.",
        (
            ("09:00", "Paradise Visitor Center", "30min", "Plan routes and check conditions."),
            ("10:00", "Skyline Trail to Myrtle Falls", "2.5h", "Classic loop with waterfall and glacier views."),
        ),
    ),
)
