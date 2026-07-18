import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Lang, Preference } from './types'

const dict = {
  en: {
    'app.title': 'Spontaneous Travel',
    'app.subtitle': 'Day trips & weekends, planned on a whim',
    'mode.surprise': 'Surprise me',
    'mode.surpriseCap': 'Ideas',
    'mode.planner': 'Trip planner',
    'mode.plannerCap': 'Plan',
    'surprise.title': 'What to do today',
    'surprise.hint': 'Activity ideas first — tap Nearby to find real places.',
    'surprise.cta': 'Surprise me',
    'surprise.moodPh': '(optional) chill / hands-on / thrill',
    'surprise.match': 'Match my mood',
    'surprise.energy': 'Energy',
    'surprise.with': 'With',
    'surprise.any': 'Any',
    'surprise.nearby': 'Nearby places',
    'surprise.hide': 'Hide places',
    'surprise.finding': 'Finding…',
    'inspiration.cta': 'Save post screenshot',
    'inspiration.bannerTitle': 'Spotted a post you love?',
    'inspiration.bannerSub': 'Upload a screenshot — we extract places, timing & must-know tips',
    'inspiration.reading': 'Reading screenshot…',
    'inspiration.note': 'Your image is analyzed once and not stored. Only planning facts are saved to your account.',
    'inspiration.loginHint': 'Log in to save to your taste profile.',
    'inspiration.places': 'Places',
    'inspiration.mustBring': 'Must bring',
    'inspiration.mustTips': 'Must-know tips',
    'inspiration.saved': 'Added to your taste profile ✓',
    'inspiration.failed': 'Could not read this screenshot',
    'planner.constraints': 'Trip constraints',
    'planner.home': 'Home base',
    'planner.tripType': 'Trip type',
    'planner.day': 'Day trip',
    'planner.weekend': 'Weekend',
    'planner.start': 'Start date',
    'planner.drive': 'Max drive',
    'planner.flight': 'Allow flights',
    'planner.prefs': 'Preferences',
    'planner.search': 'What are you in the mood for?',
    'planner.searchPh': 'e.g. forest and creek, chill beach day…',
    'planner.go': 'Find places',
    'cand.title': 'Options within range',
    'cand.nearby': 'Nearby places',
    'cand.why': 'Why',
    'cand.planning': 'Planning…',
    'cand.scope.local': 'Local fun (≤3h drive)',
    'cand.scope.regional': 'Short getaway (3–5h drive)',
    'cand.scope.distant': 'Away · long drive (5h+)',
    'cand.scope.fly': 'Away · fly',
    'cand.kind.away': 'Away (not local play)',
    'load.title': 'Planning your trip…',
    'load.sub': 'Hang tight — packing the stickers',
    'account.title': 'Account',
    'account.login': 'Log in',
    'account.register': 'Create account',
    'account.logout': 'Log out',
    'account.email': 'Email',
    'account.password': 'Password',
    'account.name': 'Display name',
    'account.persona': 'Travel persona',
    'account.quiz': 'Discover your travel persona ✨',
    'account.trips': 'My trips',
    'account.reviews': 'My reviews',
    'account.inspiration': 'Save inspiration',
    'account.language': 'Language',
    'account.about': 'About',
    'beta.fab': 'Feedback',
    'beta.title': 'Beta feedback',
    'beta.hint': 'How was this experience?',
    'beta.placeholder': 'What worked / what was confusing?',
    'beta.send': 'Send',
    'beta.sending': 'Sending…',
    'beta.thanks': 'Thanks — that helps a lot.',
    'beta.banner': 'Web beta matching the iOS app — try Surprise me or Trip planner.',
    'pref.national-park': 'National park',
    'pref.hiking': 'Hiking',
    'pref.city-walk': 'City walk',
    'pref.forest': 'Forest',
    'pref.beach': 'Beach',
  },
  zh: {
    'app.title': '说走就走',
    'app.subtitle': '临时起意的一日游 / 周末游',
    'mode.surprise': '今天干嘛',
    'mode.surpriseCap': '推玩法',
    'mode.planner': '出行规划',
    'mode.plannerCap': '做行程',
    'surprise.title': '今天干嘛',
    'surprise.hint': '先推娱乐项目；点「附近去哪」再找具体地点。',
    'surprise.cta': '随便推几个',
    'surprise.moodPh': '（可选）想轻松一点 / 想动手 / 想刺激',
    'surprise.match': '按心情推',
    'surprise.energy': '精力',
    'surprise.with': '同行',
    'surprise.any': '不限',
    'surprise.nearby': '附近去哪',
    'surprise.hide': '收起地点',
    'surprise.finding': '找附近…',
    'inspiration.cta': '保存种草截图',
    'inspiration.bannerTitle': '看到种草帖？先存下来',
    'inspiration.bannerSub': '上传截图，提取地点、时间和必带/必看',
    'inspiration.reading': '正在识别截图…',
    'inspiration.note': '截图只用于一次分析，服务器不保存原图；仅结构化事实写入你的账号。',
    'inspiration.loginHint': '登录后保存到个人口味档案。',
    'inspiration.places': '地点',
    'inspiration.mustBring': '必带',
    'inspiration.mustTips': '特别注意',
    'inspiration.saved': '已加入你的口味档案 ✓',
    'inspiration.failed': '无法从这张截图读取信息',
    'planner.constraints': '出行约束',
    'planner.home': '出发地',
    'planner.tripType': '行程类型',
    'planner.day': '一日游',
    'planner.weekend': '周末游',
    'planner.start': '出发日期',
    'planner.drive': '最长车程',
    'planner.flight': '允许飞机',
    'planner.prefs': '偏好',
    'planner.search': '你想要什么样的行程？',
    'planner.searchPh': '例如：森林溪流、轻松海边…',
    'planner.go': '开始找',
    'cand.title': '范围内的可选地点',
    'cand.nearby': '附近地点',
    'cand.why': '推荐理由',
    'cand.planning': '规划中…',
    'cand.scope.local': '本地找好玩（开车 ≤3 小时）',
    'cand.scope.regional': '短途灰度（开车 3–5 小时）',
    'cand.scope.distant': '出本地 · 长途开车（5 小时+）',
    'cand.scope.fly': '出本地 · 坐飞机',
    'cand.kind.away': '出本地（不是本地找好玩）',
    'load.title': '正在规划…',
    'load.sub': '稍等一下，贴纸还在路上',
    'account.title': '账号',
    'account.login': '登录',
    'account.register': '注册',
    'account.logout': '退出登录',
    'account.email': '邮箱',
    'account.password': '密码',
    'account.name': '昵称',
    'account.persona': '旅行人格',
    'account.quiz': '测测你的旅行人格 ✨',
    'account.trips': '我的行程',
    'account.reviews': '我的评价',
    'account.inspiration': '保存种草',
    'account.language': '语言',
    'account.about': '关于',
    'beta.fab': '反馈',
    'beta.title': 'Beta 反馈',
    'beta.hint': '这次体验怎么样？',
    'beta.placeholder': '哪里好用 / 哪里懵？',
    'beta.send': '发送',
    'beta.sending': '发送中…',
    'beta.thanks': '收到，谢谢！',
    'beta.banner': '网页 Beta，对齐 iOS：可测「今天干嘛」和「出行规划」。',
    'pref.national-park': '国家公园',
    'pref.hiking': '徒步',
    'pref.city-walk': '城市漫步',
    'pref.forest': '森林',
    'pref.beach': '海滩',
  },
} as const

type Key = keyof (typeof dict)['en']

const I18nCtx = createContext<{
  lang: Lang
  setLang: (l: Lang) => void
  t: (k: Key) => string
  prefLabel: (p: Preference) => string
} | null>(null)

function detectLang(): Lang {
  const saved = localStorage.getItem('app.language')
  if (saved === 'zh' || saved === 'en') return saved
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang)
  const setLang = (l: Lang) => {
    localStorage.setItem('app.language', l)
    setLangState(l)
  }
  const value = useMemo(
    () => ({
      lang,
      setLang,
      t: (k: Key) => dict[lang][k] ?? dict.en[k] ?? k,
      prefLabel: (p: Preference) => dict[lang][`pref.${p}` as Key] ?? p,
    }),
    [lang],
  )
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>
}

export function useI18n() {
  const ctx = useContext(I18nCtx)
  if (!ctx) throw new Error('I18nProvider missing')
  return ctx
}
