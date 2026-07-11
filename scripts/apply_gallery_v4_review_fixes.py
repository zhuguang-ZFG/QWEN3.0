#!/usr/bin/env python3
"""Apply gallery v4 review fixes to manager-mobile submodule."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MP = ROOT / "esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src"


def patch_use_device_actions() -> None:
    path = MP / "pages/v2/device-detail/composables/useDeviceActions.ts"
    text = path.read_text(encoding="utf-8")
    old = """    try {
      const download = await getGalleryDownloadUrl(image.id)
      const imageUrl = download.url
      if (!imageUrl) {
        message.alert(t('v2.detail.galleryDownloadFailed'))
        return
      }
      const r = await v2SubmitTask(deviceId(), 'draw_generated', { image_url: imageUrl, prompt: '' })
      setPhase(r.status)
      resetProgress()
      showSubmitToast('v2.detail.galleryDrawSubmitted')
      appendLog(`draw_generated(image): ${r.taskId}`)"""
    new = """    try {
      const r = await v2SubmitTask(deviceId(), 'draw_generated', {
        gallery_image_id: image.id,
        prompt: '',
      })
      setPhase(r.status)
      resetProgress()
      showSubmitToast('v2.detail.galleryDrawSubmitted')
      appendLog(`draw_generated(gallery): ${r.taskId}`)"""
    if old in text:
        text = text.replace(old, new)
    if "getGalleryDownloadUrl" in text and "gallery_image_id" in text:
        text = text.replace("import { getGalleryDownloadUrl } from '@/api/gallery'\n", "")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_gallery_panel_preview() -> None:
    path = MP / "pages/v2/device-detail/components/gallery-panel.vue"
    text = path.read_text(encoding="utf-8")
    old = """async function previewImage(image: GalleryImage) {
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
    new = """async function previewImage(image: GalleryImage) {
  try {
    const download = await getGalleryDownloadUrl(image.id)
    const urls = images.value.map((item) => {
      return item.id === image.id ? download.url : galleryThumbSrc(item)
    })
    uni.previewImage({
      current: download.url,
      urls,
    })
  }
  catch (error: any) {
    uni.showToast({ title: error?.message || t('common.fail'), icon: 'none' })
  }
}"""
    if old in text:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_gallery_ts() -> None:
    path = MP / "api/gallery/gallery.ts"
    text = path.read_text(encoding="utf-8")
    old = """export function compressGalleryUploadPath(tempFilePath: string): Promise<string> {
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
    new = """export function compressGalleryUploadPath(tempFilePath: string): Promise<string> {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    uni.compressImage({
      src: tempFilePath,
      quality: 80,
      success: (res) => resolve(res.tempFilePath || tempFilePath),
      fail: () => resolve(tempFilePath),
    })
    // #endif
    // #ifndef MP-WEIXIN
    resolve(tempFilePath)
    // #endif
  })
}

export function assertGalleryUploadSize(filePath: string, maxBytes: number): Promise<void> {
  return new Promise((resolve, reject) => {
    uni.getFileInfo({
      filePath,
      success: (info) => {
        if ((info.size ?? 0) > maxBytes) {
          reject(new Error(`file exceeds ${Math.round(maxBytes / 1024 / 1024)}MB`))
          return
        }
        resolve()
      },
      fail: () => resolve(),
    })
  })
}
"""
    if "assertGalleryUploadSize" not in text:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_gallery_panel_upload() -> None:
    path = MP / "pages/v2/device-detail/components/gallery-panel.vue"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "import { GALLERY_MAX_UPLOAD_BYTES, compressGalleryUploadPath, deleteGalleryImage, getGalleryDownloadUrl, uploadGalleryImage } from '@/api/gallery'",
        "import { GALLERY_MAX_UPLOAD_BYTES, assertGalleryUploadSize, compressGalleryUploadPath, deleteGalleryImage, getGalleryDownloadUrl, uploadGalleryImage } from '@/api/gallery'",
    )
    old = """        const uploadPath = await compressGalleryUploadPath(file.tempFilePath)
        const image = await uploadGalleryImage(uploadPath, (percent) => {"""
    new = """        const uploadPath = await compressGalleryUploadPath(file.tempFilePath)
        await assertGalleryUploadSize(uploadPath, GALLERY_MAX_UPLOAD_BYTES)
        const image = await uploadGalleryImage(uploadPath, (percent) => {"""
    if old in text and "assertGalleryUploadSize" not in text.split("chooseAndUpload")[1][:600]:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_alova_refresh_reload() -> None:
    path = MP / "pages/v2/device-detail/composables/useGalleryList.ts"
    text = path.read_text(encoding="utf-8")
    if "GALLERY_TOKEN_REFRESHED" in text:
        return
    hook = """
uni.$on?.('gallery:token-refreshed', () => {
  loadGallery(true)
})

onUnmounted(() => {
  uni.$off?.('gallery:token-refreshed')
})
"""
    text = text.replace(
        "  return {\n    images,",
        f"{hook}\n  return {{\n    images,",
    )
    if "onUnmounted" in hook and "from 'vue'" not in text:
        text = text.replace(
            "import type { GalleryImage } from '@/api/gallery'",
            "import type { GalleryImage } from '@/api/gallery'\nimport { onUnmounted } from 'vue'",
        )
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")

    alova = MP / "http/request/alova.ts"
    alova_text = alova.read_text(encoding="utf-8")
    if "gallery:token-refreshed" not in alova_text:
        alova_text = alova_text.replace(
            "        clearGalleryPreloadCache()\n        lastRefreshAt = Date.now()",
            "        clearGalleryPreloadCache()\n        uni.$emit?.('gallery:token-refreshed')\n        lastRefreshAt = Date.now()",
        )
        alova.write_text(alova_text, encoding="utf-8")
        print(f"patched {alova}")


def main() -> None:
    patch_use_device_actions()
    patch_gallery_panel_preview()
    patch_gallery_ts()
    patch_gallery_panel_upload()
    patch_alova_refresh_reload()
    print("done")


if __name__ == "__main__":
    main()
