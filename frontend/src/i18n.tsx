import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Lang = 'en' | 'zh'

const STORAGE_KEY = 'spontaneous-travel-lang'

type Dict = Record<string, string>

const TRANSLATIONS: Record<Lang, Dict> = {
  en: {
    'app.title': 'Spontaneous Travel Agent',
    'app.subtitle': 'North America day trips & weekends — plan on a whim.',
    'app.error': 'Something went wrong',
    'app.chatError': 'Sorry, I could not process that. Try again.',

    'panel.title': 'Trip constraints',
    'panel.homeBase': 'Home base',
    'panel.locating': 'Locating…',
    'panel.useLocation': '📍 Use my current location',
    'panel.geoUnsupported': 'Geolocation not supported in this browser.',
    'panel.geoFailed': 'Could not get your location — pick a city instead.',
    'panel.myLocation': 'My current location',
    'panel.tripType': 'Trip type',
    'panel.dayTrip': 'Day trip',
    'panel.weekend': 'Weekend',
    'panel.startDate': 'Start date',
    'panel.endDate': 'End date',
    'panel.maxDrive': 'Max drive time',
    'panel.includeFlight': 'Include flight-range destinations',
    'panel.preferences': 'Preferences',
    'panel.generate': 'Generate plan',
    'panel.planning': 'Planning…',

    'pref.national-park': 'National Park',
    'pref.hiking': 'Hiking',
    'pref.city-walk': 'City Walk',
    'pref.forest': 'Forest',
    'pref.beach': 'Beach',

    'chat.title': 'Refine with AI',
    'chat.hint': 'Try: “Plan a trip to Yosemite”, “Make it more relaxed”, or “Something closer”',
    'chat.thinking': 'Thinking…',
    'chat.disabled': 'Generate a plan first',
    'chat.placeholder': 'Ask to adjust the trip…',
    'chat.send': 'Send',

    'itin.empty': 'Fill in your constraints and generate a spontaneous itinerary.',
    'itin.drive': 'drive',
    'itin.alternatives': 'Alternatives',
    'itin.pack': 'Pack',

    'addr.placeholder': 'Search an address or place…',

    'map.start': 'Start',
    'map.recommended': 'Recommended',

    'cand.title': 'Options within range',
    'cand.selected': 'Selected',

    'fly.title': 'Fly-to destinations',
    'fly.loading': 'Finding flights…',
    'fly.flight': 'flight',
    'fly.from': 'from',
    'fly.searchFlights': 'Search real flights',
    'fly.searching': 'Searching flights…',
    'fly.offers': 'Flight offers',
    'fly.nonstop': 'nonstop',
    'fly.stops': 'stops',
    'fly.noLive': 'Estimated flight time shown. Add a RapidAPI key for live fares.',
    'fly.none': 'No fly-to destinations within your flight-time limit.',
    'fly.cheapestDays': 'Cheapest days',
    'itin.flight': 'flight',
  },
  zh: {
    'app.title': '说走就走旅行助手',
    'app.subtitle': '北美一日游与周末出行 —— 想走就走。',
    'app.error': '出错了',
    'app.chatError': '抱歉，我没能处理这条消息，请再试一次。',

    'panel.title': '出行条件',
    'panel.homeBase': '出发地',
    'panel.locating': '定位中…',
    'panel.useLocation': '📍 使用我的当前位置',
    'panel.geoUnsupported': '当前浏览器不支持定位。',
    'panel.geoFailed': '无法获取你的位置 —— 请改为选择城市。',
    'panel.myLocation': '我的当前位置',
    'panel.tripType': '出行类型',
    'panel.dayTrip': '一日游',
    'panel.weekend': '周末',
    'panel.startDate': '开始日期',
    'panel.endDate': '结束日期',
    'panel.maxDrive': '最长驾车时间',
    'panel.includeFlight': '包含需要飞行的目的地',
    'panel.preferences': '偏好',
    'panel.generate': '生成计划',
    'panel.planning': '规划中…',

    'pref.national-park': '国家公园',
    'pref.hiking': '徒步',
    'pref.city-walk': '城市漫步',
    'pref.forest': '森林',
    'pref.beach': '海滩',

    'chat.title': 'AI 微调',
    'chat.hint': '试试：「我要 Yosemite 的计划」「轻松一点」或「换个近一点的」',
    'chat.thinking': '思考中…',
    'chat.disabled': '请先生成计划',
    'chat.placeholder': '让我帮你调整行程…',
    'chat.send': '发送',

    'itin.empty': '填写出行条件，生成一个说走就走的行程。',
    'itin.drive': '车程',
    'itin.alternatives': '备选方案',
    'itin.pack': '打包清单',

    'addr.placeholder': '搜索地址或地点…',

    'map.start': '出发点',
    'map.recommended': '推荐',

    'cand.title': '范围内的可选地点',
    'cand.selected': '已选',

    'fly.title': '可飞往的目的地',
    'fly.loading': '正在查找航班…',
    'fly.flight': '飞行',
    'fly.from': '出发机场',
    'fly.searchFlights': '搜索真实航班',
    'fly.searching': '正在搜索航班…',
    'fly.offers': '航班选项',
    'fly.nonstop': '直飞',
    'fly.stops': '中转',
    'fly.noLive': '当前为飞行时间估算。配置 RapidAPI key 后可显示真实票价。',
    'fly.none': '在你的飞行时间上限内没有可飞目的地。',
    'fly.cheapestDays': '最便宜的日子',
    'itin.flight': '飞行',
  },
}

interface I18nContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function detectInitial(): Lang {
  const saved = localStorage.getItem(STORAGE_KEY) as Lang | null
  if (saved === 'en' || saved === 'zh') return saved
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectInitial)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, lang)
    document.documentElement.lang = lang
  }, [lang])

  const setLang = (l: Lang) => setLangState(l)
  const t = (key: string) => TRANSLATIONS[lang][key] ?? TRANSLATIONS.en[key] ?? key

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}
