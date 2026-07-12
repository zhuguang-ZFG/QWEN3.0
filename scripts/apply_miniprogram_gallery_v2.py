"""Gallery pagination, upload progress, and format helpers (v2)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MM = ROOT / "esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile"
TEMPLATES = Path(__file__).resolve().parent / "miniprogram_gallery_templates"


def _copy_template(name: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((TEMPLATES / name).read_text(encoding="utf-8"), encoding="utf-8")


def write_format_bytes() -> None:
    _copy_template("formatBytes.ts", MM / "src/utils/formatBytes.ts")


def write_use_gallery_list() -> None:
    _copy_template(
        "useGalleryList.ts",
        MM / "src/pages/v2/device-detail/composables/useGalleryList.ts",
    )


def write_gallery_api() -> None:
    _copy_template("gallery_api_v2.ts", MM / "src/api/gallery/gallery.ts")


def write_gallery_types() -> None:
    _copy_template("gallery_types_v2.ts", MM / "src/api/gallery/types.ts")


def write_gallery_panel() -> None:
    _copy_template(
        "gallery_panel_v2.vue",
        MM / "src/pages/v2/device-detail/components/gallery-panel.vue",
    )


def patch_i18n(path: Path, entries: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, value in entries.items():
        marker = f"  '{key}':"
        if marker in text:
            lines = text.splitlines()
            text = "\n".join(
                f"  '{key}': '{value}'," if line.strip().startswith(f"'{key}':") else line for line in lines
            )
        else:
            anchor = "  'v2.detail.galleryThumbFailed':"
            idx = text.find(anchor)
            if idx == -1:
                anchor = "  'v2.detail.galleryDownloadFailed':"
                idx = text.find(anchor)
            if idx == -1:
                raise RuntimeError(f"anchor missing in {path.name}")
            line_end = text.find("\n", idx)
            text = text[: line_end + 1] + f"  '{key}': '{value}',\n" + text[line_end + 1 :]
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    write_format_bytes()
    write_use_gallery_list()
    write_gallery_api()
    write_gallery_types()
    write_gallery_panel()
    patch_i18n(
        MM / "src/i18n/zh_CN.ts",
        {
            "v2.detail.galleryLoadMore": "加载更多",
            "v2.detail.galleryLoadingMore": "加载中",
        },
    )
    patch_i18n(
        MM / "src/i18n/en.ts",
        {
            "v2.detail.galleryLoadMore": "Load more",
            "v2.detail.galleryLoadingMore": "Loading",
        },
    )
    print("applied manager-mobile gallery v2 optimizations")


if __name__ == "__main__":
    main()
