# 图库预加载集成说明（P0 小程序）

将 `galleryPreload.ts` 复制到子模块：

```
esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/utils/galleryPreload.ts
```

在 `src/pages/create/components/image-picker.vue` 中：

1. `import { galleryThumbSrc, preloadGalleryThumbs } from '@/utils/galleryPreload'`
2. 列表加载成功后调用 `preloadGalleryThumbs(images)`
3. 缩略图 `:src="galleryThumbSrc(item)"`，保留 `lazy-load`

后端已提供稳定代理 `GET /device/v1/app/gallery/{id}/thumb`（JWT 或 `access_token` 查询参数）。
