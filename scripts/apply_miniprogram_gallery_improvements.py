"""Apply manager-mobile gallery UX and preload improvements (UTF-8 safe)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MM = ROOT / "esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile"
TEMPLATES = Path(__file__).resolve().parent / "miniprogram_gallery_templates"

GALLERY_PRELOAD_TS = MM / "src/utils/galleryPreload.ts"
GALLERY_PANEL_VUE = MM / "src/pages/v2/device-detail/components/gallery-panel.vue"
GALLERY_TYPES_TS = MM / "src/api/gallery/types.ts"
GALLERY_API_TS = MM / "src/api/gallery/gallery.ts"
ZH_CN = MM / "src/i18n/zh_CN.ts"
EN_TS = MM / "src/i18n/en.ts"


def _copy_template(name: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((TEMPLATES / name).read_text(encoding="utf-8"), encoding="utf-8")


def write_gallery_preload() -> None:
    _copy_template("galleryPreload.ts", GALLERY_PRELOAD_TS)


def write_gallery_panel() -> None:
    _copy_template("gallery_panel_improvements.vue", GALLERY_PANEL_VUE)


def patch_types() -> None:
    text = GALLERY_TYPES_TS.read_text(encoding="utf-8")
    if "filePath" in text:
        return
    text = text.replace(
        "  thumbPath?: string\n  tags: string[]",
        "  thumbPath?: string\n  fileUrl?: string\n  filePath?: string\n  tags: string[]",
    )
    GALLERY_TYPES_TS.write_text(text, encoding="utf-8")


def patch_gallery_api() -> None:
    text = GALLERY_API_TS.read_text(encoding="utf-8")
    if "GALLERY_MAX_UPLOAD_BYTES" in text:
        return
    text = text.replace(
        "const appPrefix = '/device/v1/app'",
        "const appPrefix = '/device/v1/app'\n\nexport const GALLERY_MAX_UPLOAD_BYTES = 10 * 1024 * 1024",
    )
    GALLERY_API_TS.write_text(text, encoding="utf-8")


def patch_i18n(path: Path, entries: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, value in entries.items():
        if key in text and f"'{key}': '{value}'" in text:
            continue
        marker = f"  '{key}':"
        if marker in text:
            lines = text.splitlines()
            out: list[str] = []
            for line in lines:
                if line.strip().startswith(f"'{key}':"):
                    out.append(f"  '{key}': '{value}',")
                else:
                    out.append(line)
            text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
        else:
            anchor = "  'v2.detail.galleryDownloadFailed':"
            idx = text.find(anchor)
            if idx == -1:
                raise RuntimeError(f"anchor missing in {path.name}")
            line_end = text.find("\n", idx)
            insert = "".join(f"  '{k}': '{v}',\n" for k, v in entries.items() if k not in text)
            if insert:
                text = text[: line_end + 1] + insert + text[line_end + 1 :]
    path.write_text(text, encoding="utf-8")


def main() -> None:
    write_gallery_preload()
    write_gallery_panel()
    patch_types()
    patch_gallery_api()
    patch_i18n(
        ZH_CN,
        {
            "v2.detail.galleryTitle": "图库绘图",
            "v2.detail.galleryDesc": "点选缩略图绘图，再次点击预览，长按删除",
            "v2.detail.gallerySelectFirst": "请先选择一张图库图片",
            "v2.detail.galleryDrawSelected": "绘制所选图片",
            "v2.detail.galleryDrawSubmitted": "图库绘图已提交",
            "v2.detail.galleryDeleteConfirm": "确定从图库删除这张图片吗？",
            "v2.detail.galleryPreview": "预览大图",
            "v2.detail.galleryTooLarge": "图片不能超过 10MB",
            "v2.detail.galleryThumbFailed": "缩略图加载失败",
        },
    )
    patch_i18n(
        EN_TS,
        {
            "v2.detail.galleryDesc": "Tap to select, tap again to preview, long-press to delete",
            "v2.detail.galleryPreview": "Preview",
            "v2.detail.galleryTooLarge": "Image must be 10MB or smaller",
            "v2.detail.galleryThumbFailed": "Thumbnail failed",
        },
    )
    print("applied manager-mobile gallery improvements")


if __name__ == "__main__":
    main()
