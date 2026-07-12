<script lang="ts" setup>
import type { GalleryImage } from '@/api/gallery'
import { GALLERY_MAX_UPLOAD_BYTES, deleteGalleryImage, listGalleryImages, uploadGalleryImage } from '@/api/gallery'
import { t } from '@/i18n'
import {
  GALLERY_PRELOAD_DEFAULT_COUNT,
  clearGalleryPreloadCache,
  galleryThumbSrc,
  preloadGalleryThumbs,
} from '@/utils/galleryPreload'

const props = defineProps<{
  deviceBusy?: boolean
  drawFromImageLoading?: boolean
}>()

const emit = defineEmits<{
  drawFromImage: [image: GalleryImage]
}>()

const images = ref<GalleryImage[]>([])
const loading = ref(false)
const uploading = ref(false)
const selectedId = ref('')
const preloadedUntil = ref(0)
const thumbErrors = ref<Record<string, boolean>>({})

const selectedImage = computed(() => images.value.find(row => row.id === selectedId.value) ?? null)

function resetPreloadState() {
  preloadedUntil.value = 0
  clearGalleryPreloadCache()
}

function preloadNextThumbs() {
  if (!images.value.length || preloadedUntil.value >= images.value.length) {
    return
  }
  preloadGalleryThumbs(images.value, {
    offset: preloadedUntil.value,
    limit: GALLERY_PRELOAD_DEFAULT_COUNT,
  })
  preloadedUntil.value = Math.min(
    preloadedUntil.value + GALLERY_PRELOAD_DEFAULT_COUNT,
    images.value.length,
  )
}

async function loadGallery() {
  loading.value = true
  try {
    const res = await listGalleryImages()
    images.value = res.images
    resetPreloadState()
    preloadNextThumbs()
  }
  catch (error: any) {
    uni.showToast({ title: error?.message || t('v2.detail.galleryLoadFailed'), icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function onGalleryScroll(event: { detail?: { scrollLeft?: number } }) {
  const scrollLeft = event.detail?.scrollLeft ?? 0
  const itemPx = uni.upx2px(176)
  const viewportPx = uni.upx2px(750)
  const visibleEnd = Math.ceil((scrollLeft + viewportPx) / Math.max(itemPx, 1))
  if (visibleEnd + GALLERY_PRELOAD_DEFAULT_COUNT > preloadedUntil.value) {
    preloadNextThumbs()
  }
}

function chooseAndUpload() {
  if (props.deviceBusy || uploading.value) {
    return
  }
  uni.chooseMedia({
    count: 1,
    mediaType: ['image'],
    success: async (res) => {
      const file = res.tempFiles?.[0]
      if (!file?.tempFilePath) {
        return
      }
      if ((file.size ?? 0) > GALLERY_MAX_UPLOAD_BYTES) {
        uni.showToast({ title: t('v2.detail.galleryTooLarge'), icon: 'none' })
        return
      }
      uploading.value = true
      try {
        const image = await uploadGalleryImage(file.tempFilePath)
        images.value = [image, ...images.value.filter(row => row.id !== image.id)]
        preloadGalleryThumbs([image])
        selectedId.value = image.id
        uni.showToast({ title: t('v2.detail.galleryUploadSuccess'), icon: 'success' })
      }
      catch (error: any) {
        uni.showToast({ title: error?.message || t('v2.detail.galleryUploadFailed'), icon: 'none' })
      }
      finally {
        uploading.value = false
      }
    },
  })
}

function selectImage(image: GalleryImage) {
  if (selectedId.value === image.id) {
    previewImage(image)
    return
  }
  selectedId.value = image.id
}

function previewImage(image: GalleryImage) {
  const urls = images.value.map(item => galleryThumbSrc(item))
  uni.previewImage({
    current: galleryThumbSrc(image),
    urls,
  })
}

function previewSelected() {
  if (!selectedImage.value) {
    uni.showToast({ title: t('v2.detail.gallerySelectFirst'), icon: 'none' })
    return
  }
  previewImage(selectedImage.value)
}

function confirmRemoveImage(image: GalleryImage) {
  uni.showModal({
    title: t('common.confirm'),
    content: t('v2.detail.galleryDeleteConfirm'),
    success: (res) => {
      if (res.confirm) {
        removeImage(image)
      }
    },
  })
}

async function removeImage(image: GalleryImage) {
  try {
    await deleteGalleryImage(image.id)
    images.value = images.value.filter(row => row.id !== image.id)
    delete thumbErrors.value[image.id]
    if (selectedId.value === image.id) {
      selectedId.value = ''
    }
    uni.showToast({ title: t('v2.detail.galleryDeleted'), icon: 'success' })
  }
  catch (error: any) {
    uni.showToast({ title: error?.message || t('common.fail'), icon: 'none' })
  }
}

function submitSelected() {
  const image = selectedImage.value
  if (!image) {
    uni.showToast({ title: t('v2.detail.gallerySelectFirst'), icon: 'none' })
    return
  }
  emit('drawFromImage', image)
}

function onThumbError(imageId: string) {
  thumbErrors.value[imageId] = true
}

onMounted(() => {
  loadGallery()
})

defineExpose({ reload: loadGallery })
</script>

<template>
  <view class="bento-card">
    <view class="title-row">
      <view class="bento-title">
        {{ t('v2.detail.galleryTitle') }}
      </view>
      <text v-if="images.length" class="count-badge">
        {{ images.length }}
      </text>
    </view>
    <text class="hint-text">
      {{ t('v2.detail.galleryDesc') }}
    </text>
    <text v-if="deviceBusy" class="busy-hint">
      {{ t('v2.detail.deviceBusyHint') }}
    </text>
    <view class="toolbar">
      <wd-button type="info" round plain size="small" :loading="uploading" :disabled="deviceBusy" @click="chooseAndUpload">
        {{ uploading ? t('v2.detail.submitting') : t('v2.detail.galleryUpload') }}
      </wd-button>
      <wd-button type="info" round plain size="small" :loading="loading" @click="loadGallery">
        {{ t('v2.detail.galleryRefresh') }}
      </wd-button>
      <wd-button
        v-if="selectedId"
        type="info"
        round
        plain
        size="small"
        @click="previewSelected"
      >
        {{ t('v2.detail.galleryPreview') }}
      </wd-button>
    </view>
    <scroll-view scroll-x class="gallery-scroll" enable-flex @scroll="onGalleryScroll">
      <view v-if="loading && !images.length" class="skeleton-row">
        <view v-for="n in 4" :key="n" class="gallery-skeleton" />
      </view>
      <view v-else-if="!images.length" class="empty-hint">
        {{ t('v2.detail.galleryEmpty') }}
      </view>
      <template v-else>
        <view
          v-for="item in images"
          :key="item.id"
          class="gallery-item"
          :class="{ selected: selectedId === item.id }"
          @click="selectImage(item)"
          @longpress="confirmRemoveImage(item)"
        >
          <view class="thumb-wrap">
            <image
              v-if="!thumbErrors[item.id]"
              class="gallery-thumb"
              lazy-load
              mode="aspectFill"
              :src="galleryThumbSrc(item)"
              @error="onThumbError(item.id)"
            />
            <view v-else class="gallery-thumb thumb-fallback">
              <text class="fallback-text">{{ t('v2.detail.galleryThumbFailed') }}</text>
            </view>
          </view>
          <text class="gallery-name">{{ item.filename }}</text>
        </view>
      </template>
    </scroll-view>
    <wd-button
      type="primary"
      round
      block
      size="large"
      class="draw-btn"
      :loading="drawFromImageLoading"
      :disabled="deviceBusy || !selectedId"
      @click="submitSelected"
    >
      {{ drawFromImageLoading ? t('v2.detail.submitting') : t('v2.detail.galleryDrawSelected') }}
    </wd-button>
  </view>
</template>

<style lang="scss" scoped>
.bento-card {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 28rpx;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.bento-title {
  font-size: 30rpx;
  font-weight: 600;
  color: var(--text);
}

.count-badge {
  min-width: 40rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  background: var(--bg2);
  color: var(--dim);
  font-size: 22rpx;
  text-align: center;
}

.hint-text {
  display: block;
  font-size: 24rpx;
  color: var(--dim);
  margin-bottom: 20rpx;
}

.busy-hint {
  display: block;
  font-size: 24rpx;
  color: var(--danger);
  margin-bottom: 12rpx;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.gallery-scroll {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
  white-space: nowrap;
  margin-bottom: 20rpx;
}

.skeleton-row {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
}

.gallery-skeleton {
  width: 160rpx;
  height: 160rpx;
  border-radius: 16rpx;
  background: linear-gradient(90deg, var(--bg2) 25%, var(--border) 37%, var(--bg2) 63%);
  background-size: 400% 100%;
  animation: gallery-shimmer 1.2s ease infinite;
}

@keyframes gallery-shimmer {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: 0 0;
  }
}

.empty-hint {
  font-size: 24rpx;
  color: var(--dim);
  padding: 12rpx 0;
}

.gallery-item {
  display: inline-flex;
  flex-direction: column;
  width: 160rpx;
  margin-right: 16rpx;
  vertical-align: top;

  &.selected .gallery-thumb,
  &.selected .thumb-fallback {
    border-color: var(--accent);
    box-shadow: 0 0 0 2rpx rgba(59, 130, 246, 0.35);
  }
}

.thumb-wrap {
  width: 160rpx;
  height: 160rpx;
}

.gallery-thumb,
.thumb-fallback {
  width: 160rpx;
  height: 160rpx;
  border-radius: 16rpx;
  border: 2rpx solid var(--border);
  background: var(--bg2);
}

.thumb-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12rpx;
}

.fallback-text {
  font-size: 20rpx;
  color: var(--dim);
  text-align: center;
}

.gallery-name {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: var(--dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.draw-btn {
  margin-top: 8rpx;
}
</style>
