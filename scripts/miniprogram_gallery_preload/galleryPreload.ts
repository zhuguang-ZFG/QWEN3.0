/**
 * Gallery thumb preload helpers for manager-mobile (uni-app / mp-weixin).
 *
 * Copy into:
 *   esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/utils/galleryPreload.ts
 *
 * Wire into image-picker.vue after gallery list loads.
 */
import { getBearerToken, getEnvBaseUrl } from '@/utils/index'

export const GALLERY_PRELOAD_DEFAULT_COUNT = 6

export type GalleryImage = {
  id: string
  thumbUrl?: string
  thumbPath?: string
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

/** Preload the first N gallery thumbs (P0). Falls back to uni.getImageInfo. */
export function preloadGalleryThumbs(images: GalleryImage[], limit = GALLERY_PRELOAD_DEFAULT_COUNT): void {
  const batch = images.slice(0, Math.max(0, limit))
  if (!batch.length) {
    return
  }
  const data = batch.map((image) => ({ type: 'image' as const, src: galleryThumbSrc(image) }))
  // #ifdef MP-WEIXIN
  if (typeof wx !== 'undefined' && typeof wx.preloadAssets === 'function') {
    wx.preloadAssets({ data })
    return
  }
  // #endif
  batch.forEach((image) => {
    uni.getImageInfo({ src: galleryThumbSrc(image) })
  })
}
