import type { GalleryImage } from '@/api/gallery'
import { getBearerToken, getEnvBaseUrl } from '@/utils'

export const GALLERY_PRELOAD_DEFAULT_COUNT = 6

const _preloadedSrc = new Set<string>()

export function clearGalleryPreloadCache(): void {
  _preloadedSrc.clear()
}

export function galleryThumbSrc(image: Pick<GalleryImage, 'id' | 'thumbPath'>): string {
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

export function preloadGalleryThumbs(
  images: Pick<GalleryImage, 'id' | 'thumbPath'>[],
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
  const wxApi = typeof wx !== 'undefined' ? (wx as any) : null
  if (wxApi?.preloadAssets) {
    wxApi.preloadAssets({ data })
    return
  }
  // #endif
  batch.forEach((src) => {
    uni.getImageInfo({ src })
  })
}
