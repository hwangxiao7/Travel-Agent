import { useEffect, useState } from 'react'
import { assetUrl } from '../api/client'

/** Bundled/public icon first; on error fall back to /api/assets/{key} (server+LRU via browser cache). */
export function AssetImg({
  iconKey,
  alt = '',
  className = 'asset-img',
  size = 48,
}: {
  iconKey?: string
  alt?: string
  className?: string
  size?: number
}) {
  const key = (iconKey || 'mascot').trim()
  const local = `/icons/${key}.webp`
  const [src, setSrc] = useState(local)

  useEffect(() => {
    setSrc(`/icons/${key}.webp`)
  }, [key])

  return (
    <img
      className={className}
      src={src}
      alt={alt || key}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      onError={() => {
        const remote = assetUrl(key)
        if (src !== remote) setSrc(remote)
      }}
    />
  )
}
