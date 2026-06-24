#!/usr/bin/env python3
"""Response examples for asset and audio endpoints."""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_assets_list() -> Any:
    return {"assets": [{"id": uuid("ast"), "title": "Cat line art"}]}


def _resp_assets_create() -> Any:
    return {"id": uuid("ast"), "title": "Cat line art"}


def _resp_asset_get() -> Any:
    return {"id": uuid("ast"), "title": "Cat line art", "prompt": "A cute cat"}


def _resp_asset_render() -> Any:
    return {"render_id": uuid("rnd"), "status": "queued"}


def _resp_voiceprints_enroll() -> Any:
    return {"voiceprint_id": uuid("vpr"), "status": "enrolling"}


def _resp_voiceprint_get() -> Any:
    return {"id": uuid("vpr"), "name": "Owner"}


def _resp_voiceprint_put() -> Any:
    return {"id": uuid("vpr"), "updated": True}


def _resp_voiceprint_delete() -> Any:
    return {"deleted": True}
