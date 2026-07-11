#!/usr/bin/env python3
"""Apply gallery v3 optimizations to manager-mobile submodule (cursorignore-safe)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MP = ROOT / "esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src"


def patch_types() -> None:
    path = MP / "api/gallery/types.ts"
    text = path.read_text(encoding="utf-8")
    if "thumbToken" in text:
        return
    text = text.replace(
        "  thumbPath?: string\n",
        "  thumbPath?: string\n  thumbToken?: string\n",
    )
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_gallery_preload() -> None:
    path = MP / "utils/galleryPreload.ts"
    text = path.read_text(encoding="utf-8")
    old = """export function galleryThumbSrc(image: Pick<GalleryImage, 'id' | 'thumbPath'>): string {
  const base = getEnvBaseUrl().replace(/\\/$/, '')
  const path = image.thumbPath || `/device/v1/app/gallery/${image.id}/thumb`
  const token = getBearerToken()
  const url = `${base}${path}`
  if (!token) {
    return url
  }
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}access_token=${encodeURIComponent(token)}`
}"""
    new = """export function galleryThumbSrc(
  image: Pick<GalleryImage, 'id' | 'thumbPath' | 'thumbToken'>,
): string {
  const base = getEnvBaseUrl().replace(/\\/$/, '')
  const path = image.thumbPath || `/device/v1/app/gallery/${image.id}/thumb`
  const url = `${base}${path}`
  if (image.thumbToken) {
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}thumb_token=${encodeURIComponent(image.thumbToken)}`
  }
  const token = getBearerToken()
  if (!token) {
    return url
  }
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}access_token=${encodeURIComponent(token)}`
}"""
    if old not in text:
        if "thumb_token" in text:
            return
        raise SystemExit(f"galleryPreload.ts pattern mismatch: {path}")
    text = text.replace(old, new)
    text = text.replace(
        "  images: Pick<GalleryImage, 'id' | 'thumbPath'>[],",
        "  images: Pick<GalleryImage, 'id' | 'thumbPath' | 'thumbToken'>[],",
    )
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_gallery_ts() -> None:
    path = MP / "api/gallery/gallery.ts"
    text = path.read_text(encoding="utf-8")
    if "compressGalleryUploadPath" in text:
        return
    insert = """
export function compressGalleryUploadPath(tempFilePath: string): Promise<string> {
  return new Promise((resolve) => {
    uni.compressImage({
      src: tempFilePath,
      quality: 80,
      success: (res) => resolve(res.tempFilePath || tempFilePath),
      fail: () => resolve(tempFilePath),
    })
  })
}

"""
    text = text.replace(
        "export const GALLERY_PAGE_SIZE = 24\n\n",
        f"export const GALLERY_PAGE_SIZE = 24\n{insert}",
    )
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_gallery_panel() -> None:
    path = MP / "pages/v2/device-detail/components/gallery-panel.vue"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "import { GALLERY_MAX_UPLOAD_BYTES, deleteGalleryImage, uploadGalleryImage } from '@/api/gallery'",
        "import { GALLERY_MAX_UPLOAD_BYTES, compressGalleryUploadPath, deleteGalleryImage, getGalleryDownloadUrl, uploadGalleryImage } from '@/api/gallery'",
    )
    old_upload = """      uploading.value = true
      uploadProgress.value = 0
      try {
        const image = await uploadGalleryImage(file.tempFilePath, (percent) => {"""
    new_upload = """      uploading.value = true
      uploadProgress.value = 0
      try {
        const uploadPath = await compressGalleryUploadPath(file.tempFilePath)
        const image = await uploadGalleryImage(uploadPath, (percent) => {"""
    if old_upload in text and "compressGalleryUploadPath" not in text.split("chooseAndUpload")[1][:800]:
        text = text.replace(old_upload, new_upload)

    old_preview = """function previewImage(image: GalleryImage) {
  uni.previewImage({
    current: galleryThumbSrc(image),
    urls: images.value.map(item => galleryThumbSrc(item)),
  })
}"""
    new_preview = """async function previewImage(image: GalleryImage) {
  try {
    const download = await getGalleryDownloadUrl(image.id)
    uni.previewImage({
      current: download.url,
      urls: [download.url],
    })
  }
  catch (error: any) {
    uni.showToast({ title: error?.message || t('common.fail'), icon: 'none' })
  }
}"""
    if old_preview in text:
        text = text.replace(old_preview, new_preview)
    elif "getGalleryDownloadUrl" not in text:
        raise SystemExit(f"gallery-panel preview pattern mismatch: {path}")

    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_alova() -> None:
    path = MP / "http/request/alova.ts"
    text = path.read_text(encoding="utf-8")
    if "clearGalleryPreloadCache" in text:
        return
    text = text.replace(
        "import { getEnvBaseUrl } from '@/utils'\n",
        "import { getEnvBaseUrl } from '@/utils'\nimport { clearGalleryPreloadCache } from '@/utils/galleryPreload'\n",
    )
    text = text.replace(
        "        await v2RefreshToken()\n        lastRefreshAt = Date.now()",
        "        await v2RefreshToken()\n        clearGalleryPreloadCache()\n        lastRefreshAt = Date.now()",
    )
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def main() -> None:
    patch_types()
    patch_gallery_preload()
    patch_gallery_ts()
    patch_gallery_panel()
    patch_alova()
    print("done")


if __name__ == "__main__":
    main()
