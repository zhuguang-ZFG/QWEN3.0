<!--
  Integration snippet for image-picker.vue (manager-mobile).

  1. import { preloadGalleryThumbs } from '@/utils/galleryPreload'
  2. After gallery list API resolves:
       preloadGalleryThumbs(images)
  3. Bind grid thumbnails with galleryThumbSrc(image) instead of raw Telegram URLs.
-->
<template>
  <scroll-view scroll-y class="gallery-grid">
    <image
      v-for="item in images"
      :key="item.id"
      class="gallery-thumb"
      lazy-load
      mode="aspectFill"
      :src="thumbSrc(item)"
      @tap="selectImage(item)"
    />
  </scroll-view>
</template>

<script setup lang="ts">
import { galleryThumbSrc, preloadGalleryThumbs, type GalleryImage } from '@/utils/galleryPreload'

const images = ref<GalleryImage[]>([])

function thumbSrc(item: GalleryImage) {
  return galleryThumbSrc(item)
}

async function loadGallery() {
  const res = await listGalleryImages()
  images.value = res.images ?? []
  preloadGalleryThumbs(images.value)
}

function selectImage(item: GalleryImage) {
  // unchanged: GET /gallery/{id}/download then draw_from_image
}
</script>
