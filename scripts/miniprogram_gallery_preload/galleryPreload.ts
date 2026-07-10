/**
 * Gallery thumb preload helpers for manager-mobile (uni-app / mp-weixin).
 */
import { getBearerToken, getEnvBaseUrl } from '@/utils/index'

export const GALLERY_PRELOAD_DEFAULT_COUNT = 6

const _preloadedSrc = new Set<string>()

export type GalleryImage = {
  id: string
  thumbPath?: string
}

export function clearGalleryPreloadCache(): void {
  _preloadedSrc.clear()
}

/** Build an authenticated thumb URL suitable for <image src> and wx.preloadAssets. */
export function galleryThumbSrc(image: GalleryImage): string {
  const base = getEnvBaseUrl().replace(/\/$/, '')
  const path = image.thumbPath || `/device/v1/app/gallery/${image.id}/thumb`
  const token = getBearerToken()
  const url = `${base}${path}`
  if (!token) {
    return url
  }
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}access_token=${encodeURIComponent(token)}`
}

export type GalleryPreloadOptions = {
  offset?: number
  limit?: number
}

/** Preload gallery thumbs in batches (P0/P1). Falls back to uni.getImageInfo. */
export function preloadGalleryThumbs(
  images: GalleryImage[],
  options: number | GalleryPreloadOptions = GALLERY_PRELOAD_DEFAULT_COUNT,
): void {
  const offset = typeof options === 'number' ? 0 : (options.offset ?? 0)
  const limit = typeof options === 'number' ? options : (options.limit ?? GALLERY_PRELOAD_DEFAULT_COUNT)
  const batch = images
    .slice(offset, offset + Math.max(0, limit))
    .map(image => galleryThumbSrc(image))
    .filter((src) => {
      if (_preloadedSrc.has(src)) {
        return false
      }
      _preloadedSrc.add(src)
      return true
    })
  if (!batch.length) {
    return
  }
  const data = batch.map(src => ({ type: 'image' as const, src }))
  // #ifdef MP-WEIXIN
  if (typeof wx !== 'undefined' && typeof wx.preloadAssets === 'function') {
    wx.preloadAssets({ data })
    return
  }
  // #endif
  batch.forEach((src) => {
    uni.getImageInfo({ src })
  })
}
