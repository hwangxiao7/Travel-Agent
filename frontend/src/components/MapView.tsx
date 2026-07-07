import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import type { Candidate, Location } from '../types'

interface Props {
  origin: Location
  candidates: Candidate[]
  selected?: { lat: number; lng: number; name: string } | null
}

export function MapView({ origin, candidates, selected }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const token = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    if (!token) return

    mapboxgl.accessToken = token
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/outdoors-v12',
      center: [origin.lng, origin.lat],
      zoom: 7,
    })
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [origin.lat, origin.lng, token])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !token) return

    const markers: mapboxgl.Marker[] = []

    const originMarker = new mapboxgl.Marker({ color: '#2563eb' })
      .setLngLat([origin.lng, origin.lat])
      .setPopup(new mapboxgl.Popup().setText(`Start: ${origin.label || 'Home'}`))
      .addTo(map)
    markers.push(originMarker)

    candidates.forEach((c, i) => {
      const color = selected?.name === c.name ? '#16a34a' : i === 0 ? '#ea580c' : '#64748b'
      const m = new mapboxgl.Marker({ color })
        .setLngLat([c.lng, c.lat])
        .setPopup(
          new mapboxgl.Popup().setHTML(
            `<strong>${c.name}</strong><br/>${c.drive_time} drive<br/><em>${c.highlight}</em>`,
          ),
        )
        .addTo(map)
      markers.push(m)
    })

    if (candidates.length > 0) {
      const bounds = new mapboxgl.LngLatBounds()
      bounds.extend([origin.lng, origin.lat])
      candidates.forEach((c) => bounds.extend([c.lng, c.lat]))
      map.fitBounds(bounds, { padding: 48, maxZoom: 9 })
    }

    return () => markers.forEach((m) => m.remove())
  }, [candidates, origin, selected, token])

  if (!token) {
    return (
      <div className="map-fallback">
        <p>Add <code>VITE_MAPBOX_TOKEN</code> to <code>frontend/.env</code> for the interactive map.</p>
        <ul>
          {candidates.map((c) => (
            <li key={c.name}>
              <strong>{c.name}</strong> — {c.drive_time}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return <div ref={containerRef} className="map-container" />
}
