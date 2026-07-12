export interface GalleryImage {
  id: string
  accountId: string
  fileId: string
  filename: string
  mimeType: string
  sizeBytes: number
  thumbUrl?: string
  thumbPath?: string
  fileUrl?: string
  filePath?: string
  tags: string[]
  status: string
  createdAt?: string
}

export interface GalleryListResponse {
  images: GalleryImage[]
  count: number
  total: number
}

export interface GalleryDownloadResponse {
  url: string
}
