"""Tests for extracted chat handler modules (CQ-014 slice 4)."""

import asyncio

import pytest
from fastapi import HTTPException

import routes.chat_handler as chat_handler
import routes.chat_support as chat_support
from chat_models import ChatRequest, Message


def test_attach_memory_recall_meta_adds_x_lima_meta():
    response = {"choices": []}
    meta = {"checked": True, "applied": True, "recalled_memory_ids": ["m1"]}
    result = chat_support.attach_memory_recall_meta(response, meta)
    assert result["x_lima_meta"]["memory_recall"] == meta


def test_handle_chat_rejects_empty_query():
    req = ChatRequest(model="lima-1.3", messages=[Message(role="user", content="   ")])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(chat_handler.handle_chat(req))

    assert exc.value.status_code == 400


def test_handle_chat_is_reexported_on_server():
    import server

    assert server._handle_chat is chat_handler.handle_chat
