import { getToken } from './api/client'
import { API_BASE } from './api/endpoints'
import type { Location } from './types'

export type LikeKind = 'activity' | 'destination'

type Pending = {
  op: 'like' | 'unlike'
  kind: LikeKind
  key: string
  name: string
  tags: string[]
  blurb: string
}

const STORAGE_KEY = 'travel.like.ids'
const listeners = new Set<() => void>()

let liked = new Set<string>(loadLocal())
let pending: Pending[] = []
let origin: Location = { lat: 0, lng: 0, label: '' }
let timer: ReturnType<typeof setTimeout> | null = null
let version = 0

function id(kind: LikeKind, key: string) {
  return `${kind}:${key}`
}

function loadLocal(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...liked]))
}

function notify() {
  version += 1
  listeners.forEach((l) => l())
}

export function subscribeLikes(fn: () => void) {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

export function likesVersion() {
  return version
}

export function isLiked(kind: LikeKind, key: string) {
  return liked.has(id(kind, key))
}

export function setLikeOrigin(loc: Location) {
  origin = loc
}

export function toggleLike(input: {
  kind: LikeKind
  key: string
  name: string
  tags?: string[]
  blurb?: string
}): boolean {
  const k = id(input.kind, input.key)
  const nowLiked = !liked.has(k)
  if (nowLiked) liked.add(k)
  else liked.delete(k)
  pending = pending.filter((p) => !(p.kind === input.kind && p.key === input.key))
  pending.push({
    op: nowLiked ? 'like' : 'unlike',
    kind: input.kind,
    key: input.key,
    name: input.name,
    tags: input.tags || [],
    blurb: input.blurb || '',
  })
  persist()
  notify()
  scheduleFlush()
  return nowLiked
}

function scheduleFlush() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    void flushLikes()
  }, 2500)
  if (pending.length >= 5) {
    if (timer) clearTimeout(timer)
    void flushLikes()
  }
}

export async function flushLikes() {
  if (!pending.length) return
  if (!getToken()) {
    // Keep pending until logged in; UI like state still local.
    return
  }
  const batch = pending
  pending = []
  try {
    const res = await fetch(`${API_BASE}/api/likes/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ items: batch, origin }),
    })
    if (!res.ok) throw new Error('flush failed')
  } catch {
    for (const p of batch.reverse()) {
      if (!pending.some((x) => x.kind === p.kind && x.key === p.key)) pending.unshift(p)
    }
  }
}
