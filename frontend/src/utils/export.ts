import type { Itinerary, Location } from '../types'

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

// Accepts "09:00", "9:00 AM", "1:30 PM" -> [hours24, minutes]
function parseTime(time: string): [number, number] {
  const m = time.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i)
  if (!m) return [9, 0]
  let hh = Number(m[1])
  const mm = Number(m[2])
  const ap = m[3]?.toUpperCase()
  if (ap === 'PM' && hh < 12) hh += 12
  if (ap === 'AM' && hh === 12) hh = 0
  return [Math.min(hh, 23), Math.min(mm, 59)]
}

// "1.5h", "45min", "2h" -> minutes (fallback 60)
function durationMinutes(dur: string): number {
  let total = 0
  const h = dur.match(/([\d.]+)\s*h/i)
  const min = dur.match(/(\d+)\s*min/i)
  if (h) total += Math.round(parseFloat(h[1]) * 60)
  if (min) total += Number(min[1])
  return total || 60
}

function stampFrom(date: Date): string {
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `T${pad(date.getHours())}${pad(date.getMinutes())}00`
  )
}

// Floating local-time stamps so events land on the traveler's own clock.
function eventStamps(date: string, time: string, dur: string): [string, string] {
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = parseTime(time)
  const start = new Date(y, m - 1, d, hh, mm)
  const end = new Date(start.getTime() + durationMinutes(dur) * 60000)
  return [stampFrom(start), stampFrom(end)]
}

function escapeICS(text: string): string {
  return (text || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n')
}

export function buildICS(itinerary: Itinerary): string {
  const now = new Date()
  const dtstamp =
    `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}` +
    `T${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}Z`

  const lines: string[] = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Spontaneous Travel Agent//EN',
    'CALSCALE:GREGORIAN',
  ]

  itinerary.days.forEach((day, di) => {
    day.activities.forEach((a, ai) => {
      const [start, end] = eventStamps(day.date, a.time, a.duration)
      lines.push(
        'BEGIN:VEVENT',
        `UID:${day.date}-${di}-${ai}-${Math.random().toString(36).slice(2, 8)}@spontaneous-travel`,
        `DTSTAMP:${dtstamp}`,
        `DTSTART:${start}`,
        `DTEND:${end}`,
        `SUMMARY:${escapeICS(a.place)}`,
        `LOCATION:${escapeICS(itinerary.destination)}`,
        `DESCRIPTION:${escapeICS(a.note)}`,
        'END:VEVENT',
      )
    })
  })

  lines.push('END:VCALENDAR')
  return lines.join('\r\n')
}

export function downloadICS(itinerary: Itinerary): void {
  const blob = new Blob([buildICS(itinerary)], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const safe = itinerary.destination.replace(/[^\w-]+/g, '-').replace(/^-+|-+$/g, '')
  a.href = url
  a.download = `${safe || 'itinerary'}.ics`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function googleMapsUrl(origin: Location | undefined, itinerary: Itinerary): string {
  const dest = `${itinerary.destination_lat},${itinerary.destination_lng}`
  const mode = itinerary.travel_mode === 'fly' ? 'transit' : 'driving'
  if (origin) {
    return `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${dest}&travelmode=${mode}`
  }
  return `https://www.google.com/maps/search/?api=1&query=${dest}`
}

export function buildShareText(itinerary: Itinerary): string {
  const head =
    itinerary.travel_mode === 'fly'
      ? `${itinerary.destination} · ✈ ${itinerary.origin_airport} → ${itinerary.destination_airport} (${itinerary.drive_time})`
      : `${itinerary.destination} · ${itinerary.drive_time} drive`
  const lines: string[] = [head]
  if (itinerary.summary) lines.push(itinerary.summary)
  itinerary.days.forEach((day) => {
    lines.push('', day.date)
    day.activities.forEach((a) => {
      lines.push(`  ${a.time}  ${a.place}${a.duration ? ` (${a.duration})` : ''}`)
    })
  })
  return lines.join('\n')
}

export async function copyShareText(itinerary: Itinerary): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(buildShareText(itinerary))
    return true
  } catch {
    return false
  }
}
