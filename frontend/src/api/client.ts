import type { ChatMessage, Itinerary, PlanRequest, PlanResponse, Preference } from '../types'

export async function createPlan(body: PlanRequest): Promise<PlanResponse> {
  const res = await fetch('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to generate plan')
  }
  return res.json()
}

export async function sendChat(
  messages: ChatMessage[],
  currentItinerary: Itinerary | null,
  origin: { lat: number; lng: number; label: string } | null,
  preferences: Preference[],
  language: string,
): Promise<{ reply: string; itinerary: Itinerary | null }> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages,
      current_itinerary: currentItinerary,
      origin,
      preferences,
      language,
    }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}
