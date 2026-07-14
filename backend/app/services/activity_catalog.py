"""Curated ACTIVITY catalog — the "娱乐项目" plane (shop-independent).

Product insight (from real RED "100件快乐小事 / 30种线下活动" posts): the unit
users want when they think "不知道今天干嘛" is an ACTIVITY (泡温泉, 扔斧头, 滑翔伞,
剧本杀, 露营, 抓小龙虾), NOT a specific shop. So this catalog stores activity
*types* with plan metadata (duration / season / vibe / companion / energy /
cost). Matching is open-vocab (embeddings over the blurb+tags — no keyword
index). The concrete venue is resolved lazily later (OSM/Places) only if the
user picks it, keeping recommendations independent of any merchant.

This is the reliable cold-start backbone: works with zero social data, zero keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Activity:
    key: str
    name_en: str
    name_zh: str
    tags: tuple[str, ...]          # open-vocab vibe/type for persona matching
    duration_h: float              # typical time to budget
    energy: str                    # low | medium | high
    cost: str                      # $ | $$ | $$$
    companion: tuple[str, ...]     # solo / date / family / friends / group
    indoor: bool
    months: tuple[int, ...] = field(default_factory=tuple)  # season (empty = year-round)
    blurb: str = ""                # one-line "how to play" plan hint

    def text(self) -> str:
        """Natural-language representation used for embedding/matching."""
        who = ", ".join(self.companion)
        season = "seasonal" if self.months else "year-round"
        return (
            f"{self.name_en} ({self.name_zh}). {self.blurb} "
            f"Vibe: {', '.join(self.tags)}. Good for: {who}. "
            f"{'Indoor' if self.indoor else 'Outdoor'}, {self.energy} energy, {season}, ~{self.duration_h}h, {self.cost}."
        )


_SUMMER = (5, 6, 7, 8, 9)
_WARM = (4, 5, 6, 7, 8, 9, 10)


# Distilled from the RED activity-list screenshots (Bay Area 100件 / 30种线下活动 …).
ACTIVITIES: tuple[Activity, ...] = (
    # ── Outdoor / adrenaline ─────────────────────────────────────────────
    Activity("paragliding", "Paragliding", "滑翔伞", ("outdoor", "adventure", "thrill", "scenic", "hands-on"),
             3.0, "high", "$$$", ("friends", "date"), False, _WARM,
             "Tandem glide off a coastal ridge — book a certified pilot, ~15–30 min air time."),
    Activity("skydiving", "Skydiving", "跳伞", ("outdoor", "adventure", "thrill", "bucket-list"),
             4.0, "high", "$$$", ("friends", "solo"), False, _WARM,
             "Tandem jump at a regional dropzone; half a day incl. briefing."),
    Activity("zipline", "Ziplining", "高空滑索", ("outdoor", "adventure", "thrill", "forest"),
             2.5, "medium", "$$", ("friends", "family"), False, _WARM,
             "Canopy zipline course through the trees."),
    Activity("hot_air_balloon", "Hot-air balloon ride", "热气球", ("outdoor", "scenic", "romantic", "bucket-list"),
             4.0, "low", "$$$", ("date", "friends"), False, _WARM,
             "Sunrise balloon over wine country; book dawn slot, dress warm."),
    Activity("go_kart", "Go-karting", "卡丁车", ("adventure", "thrill", "indoor", "friends"),
             2.0, "medium", "$$", ("friends", "group"), True, (),
             "Race an indoor/outdoor track — great small-group competition."),
    Activity("indoor_climbing", "Indoor rock climbing", "室内攀岩", ("active", "hands-on", "indoor", "sport"),
             2.0, "high", "$$", ("solo", "friends", "date"), True, (),
             "Bouldering/top-rope gym; rent shoes, no experience needed."),
    Activity("axe_throwing", "Axe throwing", "扔斧头", ("indoor", "thrill", "hands-on", "friends", "quirky"),
             1.5, "medium", "$$", ("friends", "group", "date"), True, (),
             "Lane-based axe throwing venue; coached, book a lane."),
    Activity("archery", "Archery", "射箭", ("hands-on", "focus", "sport", "quirky"),
             1.5, "medium", "$$", ("friends", "solo", "date"), True, (),
             "Target archery range; intro lesson + range time."),
    Activity("shooting_range", "Shooting range", "射击", ("indoor", "thrill", "focus", "hands-on"),
             1.5, "medium", "$$", ("friends", "solo"), True, (),
             "Indoor range; stress-release, gear rental available."),
    Activity("surfing", "Surfing", "冲浪", ("outdoor", "water", "sport", "beach", "adventure"),
             3.0, "high", "$$", ("solo", "friends"), False, _WARM,
             "Beginner surf lesson + board/wetsuit rental at a mellow break."),
    Activity("trampoline", "Trampoline park", "蹦床", ("indoor", "active", "playful", "family"),
             1.5, "high", "$$", ("family", "friends"), True, (),
             "Jump park; grippy socks, great with kids or friends."),

    # ── Water / nature-chill ─────────────────────────────────────────────
    Activity("sup", "Stand-up paddleboarding", "桨板 SUP", ("outdoor", "water", "relaxing", "scenic", "active"),
             2.5, "medium", "$$", ("solo", "date", "friends"), False, _WARM,
             "Rent a SUP on calm water; sunrise/sunset is best."),
    Activity("kayak", "Kayaking", "皮划艇", ("outdoor", "water", "active", "nature"),
             3.0, "medium", "$$", ("friends", "date", "family"), False, _WARM,
             "Paddle a bay/estuary; guided tours spot wildlife."),
    Activity("whale_watching", "Whale watching", "出海观鲸", ("outdoor", "water", "nature", "scenic", "wildlife"),
             4.0, "low", "$$", ("family", "date", "friends"), False, _WARM,
             "Boat tour from the harbor; mornings are calmer, bring layers."),
    Activity("crayfishing", "Crayfishing / creek fishing", "抓小龙虾", ("outdoor", "water", "foraging", "hands-on", "playful"),
             2.5, "medium", "$", ("family", "friends"), False, _SUMMER,
             "Net crayfish at a creek/lake — bring a bucket; casual and cheap."),
    Activity("snorkeling", "Snorkeling", "浮潜", ("outdoor", "water", "nature", "adventure"),
             3.0, "medium", "$$", ("friends", "date"), False, _SUMMER,
             "Snorkel a cove/kelp forest; rent gear, check water temp."),
    Activity("rafting", "Summer river floating/rafting", "夏日漂流", ("outdoor", "water", "playful", "friends"),
             4.0, "medium", "$$", ("friends", "group"), False, _SUMMER,
             "Lazy float or light rapids down a river; go with a group."),
    Activity("sailing", "Sailing", "帆船出海", ("outdoor", "water", "scenic", "relaxing"),
             3.0, "low", "$$$", ("date", "friends"), False, _WARM,
             "Skippered day-sail on the bay; no experience needed."),
    Activity("hot_spring", "Hot springs", "泡温泉", ("outdoor", "water", "relaxing", "wellness", "nature"),
             3.0, "low", "$$", ("date", "solo", "friends"), False, (),
             "Soak at natural/forest hot springs; best on a cool day."),

    # ── Chill outdoor / scenic ───────────────────────────────────────────
    Activity("camping", "Camping", "露营", ("outdoor", "nature", "relaxing", "adventure"),
             12.0, "medium", "$", ("friends", "family", "date"), False, _WARM,
             "Overnight or car-camp; stargaze + campfire."),
    Activity("hiking", "Hiking a scenic trail", "徒步", ("outdoor", "nature", "active", "scenic", "hidden-gem"),
             3.0, "medium", "$", ("solo", "friends", "date"), False, (),
             "Pick a trail by view/effort; go early to beat crowds."),
    Activity("cycling", "Cycling / bike ride", "骑行", ("outdoor", "active", "scenic", "explore"),
             2.5, "medium", "$", ("solo", "friends", "family"), False, (),
             "Rent bikes for a waterfront or park loop."),
    Activity("picnic", "Picnic in a park", "野餐", ("outdoor", "relaxing", "chill", "social", "aesthetic"),
             2.5, "low", "$", ("date", "friends", "family"), False, _WARM,
             "Grab snacks, a blanket, and a good lawn/viewpoint."),
    Activity("sunset_view", "Sunset / viewpoint", "看日落", ("outdoor", "scenic", "romantic", "relaxing", "photography"),
             1.5, "low", "$", ("date", "solo", "friends"), False, (),
             "Drive/walk to an overlook for golden hour."),
    Activity("stargazing", "Stargazing", "看星星", ("outdoor", "night", "quiet", "nature", "romantic"),
             2.5, "low", "$", ("date", "solo", "friends"), False, (),
             "Head to a dark-sky spot away from city lights."),
    Activity("botanical_garden", "Botanical garden / flower market", "植物园/花市", ("outdoor", "quiet", "aesthetic", "photography", "relaxing"),
             2.0, "low", "$", ("solo", "date", "family"), False, _WARM,
             "Wander gardens or a flower market; buy yourself a bunch."),
    Activity("u_pick", "Fruit / berry picking", "摘水果", ("outdoor", "foraging", "family", "seasonal", "hands-on"),
             2.5, "low", "$", ("family", "date", "friends"), False, _WARM,
             "U-pick farm — cherries/berries/apples by season."),
    Activity("farm_animals", "Farm / animal feeding", "农场喂动物", ("outdoor", "family", "wholesome", "nature"),
             2.5, "low", "$", ("family",), False, _WARM,
             "Petting/working farm; great with kids."),
    Activity("horse_riding", "Beach / trail horseback riding", "骑马", ("outdoor", "nature", "scenic", "adventure"),
             2.0, "medium", "$$", ("date", "friends"), False, _WARM,
             "Guided beach or trail ride; book ahead."),

    # ── Creative / hands-on ──────────────────────────────────────────────
    Activity("pottery", "Pottery / ceramics", "陶艺", ("indoor", "creative", "hands-on", "relaxing", "date"),
             2.0, "low", "$$", ("date", "solo", "friends"), True, (),
             "Wheel-throwing or hand-building class; take home a piece."),
    Activity("painting", "Painting / art class", "画画", ("indoor", "creative", "relaxing", "aesthetic"),
             2.0, "low", "$$", ("date", "solo", "friends"), True, (),
             "Sip-and-paint or open studio session."),
    Activity("floral", "Floral arranging", "花艺", ("indoor", "creative", "aesthetic", "relaxing"),
             1.5, "low", "$$", ("date", "solo", "friends"), True, (),
             "Make a bouquet in a hands-on floral workshop."),
    Activity("baking", "Baking / dessert class", "烘焙", ("indoor", "creative", "food", "hands-on", "wholesome"),
             2.5, "low", "$$", ("date", "friends", "family"), True, (),
             "Learn to bake bread/pastry; eat what you make."),
    Activity("candle_diy", "Candle / scent DIY", "香薰蜡烛DIY", ("indoor", "creative", "aesthetic", "relaxing"),
             1.5, "low", "$$", ("date", "solo", "friends"), True, (),
             "Blend and pour your own scented candle."),
    Activity("cooking_class", "Cooking class", "烹饪课", ("indoor", "creative", "food", "hands-on", "social"),
             2.5, "medium", "$$", ("date", "friends", "family"), True, (),
             "Hands-on class for a cuisine you love."),

    # ── Social / night / play ────────────────────────────────────────────
    Activity("escape_room", "Escape room", "密室逃脱", ("indoor", "puzzle", "social", "thrill", "friends"),
             1.5, "medium", "$$", ("friends", "group", "date"), True, (),
             "60-min themed room; best with 3–6 people."),
    Activity("board_games", "Board games / murder mystery", "桌游/剧本杀", ("indoor", "social", "puzzle", "playful", "friends"),
             3.0, "low", "$", ("friends", "group"), True, (),
             "Board-game café or a scripted murder-mystery (剧本杀)."),
    Activity("ktv", "Karaoke", "KTV", ("indoor", "social", "playful", "night", "friends"),
             2.5, "medium", "$$", ("friends", "group"), True, (),
             "Private karaoke room; snacks + drinks, let loose."),
    Activity("bowling", "Bowling", "保龄球", ("indoor", "social", "playful", "friends"),
             2.0, "low", "$$", ("friends", "family", "date"), True, (),
             "Classic lanes; easy low-pressure hangout."),
    Activity("arcade", "Retro arcade", "复古街机", ("indoor", "playful", "nostalgic", "social"),
             1.5, "low", "$", ("friends", "date"), True, (),
             "Barcade with classic cabinets and pinball."),
    Activity("roller_skating", "Roller skating", "滑旱冰", ("indoor", "active", "playful", "nostalgic", "social"),
             2.0, "medium", "$", ("friends", "date", "family"), True, (),
             "Roller rink night; rent skates."),
    Activity("mini_golf", "Mini golf", "迷你高尔夫", ("playful", "family", "date", "casual"),
             1.5, "low", "$", ("date", "family", "friends"), False, (),
             "Themed putt-putt course; low-key and fun."),
    Activity("comedy", "Stand-up comedy", "脱口秀", ("indoor", "night", "social", "entertainment"),
             2.0, "low", "$$", ("date", "friends"), True, (),
             "Comedy club set; grab a drink."),
    Activity("live_music", "Live music / livehouse", "音乐现场", ("indoor", "night", "music", "social", "energetic"),
             3.0, "medium", "$$", ("friends", "date"), True, (),
             "Catch a small-venue gig; check the local listings."),
    Activity("open_air_cinema", "Open-air movie", "露天电影", ("outdoor", "relaxing", "romantic", "night", "chill"),
             2.5, "low", "$", ("date", "family", "friends"), False, _WARM,
             "Bring a blanket to an outdoor film screening."),

    # ── Culture / slow ───────────────────────────────────────────────────
    Activity("museum", "Museum / immersive exhibit", "看展/美术馆", ("indoor", "culture", "aesthetic", "quiet"),
             2.5, "low", "$$", ("solo", "date", "friends"), True, (),
             "Art museum or immersive exhibit; check special shows."),
    Activity("bookstore_cafe", "Bookstore + café afternoon", "书店+咖啡", ("indoor", "quiet", "cozy", "relaxing", "solo"),
             2.0, "low", "$", ("solo", "date"), True, (),
             "Slow afternoon browsing books over coffee."),
    Activity("flea_market", "Flea / vintage market", "跳蚤市场", ("outdoor", "explore", "aesthetic", "quirky", "social"),
             2.0, "low", "$", ("friends", "date", "solo"), False, _WARM,
             "Thrift a flea/vintage market for treasures."),
    Activity("farmers_market", "Farmers market", "农夫市集", ("outdoor", "food", "local", "wholesome", "social"),
             1.5, "low", "$", ("family", "date", "friends"), False, _WARM,
             "Graze a farmers market; buy flowers + local food."),

    # ── Wellness ─────────────────────────────────────────────────────────
    Activity("yoga", "Yoga / dance class", "瑜伽/舞蹈课", ("indoor", "wellness", "active", "relaxing"),
             1.5, "medium", "$", ("solo", "friends"), True, (),
             "Drop-in class; reset body and mind."),
    Activity("boxing", "Boxing / martial arts class", "拳击课", ("indoor", "active", "sport", "energetic"),
             1.5, "high", "$$", ("solo", "friends"), True, (),
             "Try a boxing/muay-thai intro; great stress release."),
    Activity("meditation", "Meditation / sound bath", "冥想", ("indoor", "wellness", "quiet", "relaxing"),
             1.5, "low", "$", ("solo",), True, (),
             "Guided meditation or sound-bath workshop."),
)


ACTIVITY_BY_KEY = {a.key: a for a in ACTIVITIES}
