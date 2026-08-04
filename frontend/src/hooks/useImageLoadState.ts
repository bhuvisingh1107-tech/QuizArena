import { useCallback, useLayoutEffect, useRef, useState } from 'react'

/**
 * Track whether an <img> has finished loading for the current `src` / load key.
 *
 * Cached images often set `complete` before React attaches `onLoad`, which
 * leaves UI stuck on a loading skeleton when the same media URL is reused
 * across questions (apply-image-to-all).
 */
export function useImageLoadState(src: string | null) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const nodeRef = useRef<HTMLImageElement | null>(null)

  const syncFromElement = useCallback((el: HTMLImageElement | null) => {
    if (el && el.complete && el.naturalWidth > 0) {
      setLoaded(true)
      return
    }
    setLoaded(false)
  }, [])

  useLayoutEffect(() => {
    setFailed(false)
    syncFromElement(nodeRef.current)
  }, [src, syncFromElement])

  const imgRef = useCallback(
    (el: HTMLImageElement | null) => {
      nodeRef.current = el
      if (!src) {
        setLoaded(false)
        return
      }
      // Ref attach runs when the node mounts — catch cache before onLoad.
      if (el && el.complete && el.naturalWidth > 0) {
        setLoaded(true)
      }
    },
    [src],
  )

  return {
    imgRef,
    failed,
    loaded,
    onLoad: () => setLoaded(true),
    onError: () => setFailed(true),
  }
}
