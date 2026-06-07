"""Tests for OpenViking HTTP client wrapper."""
from unittest.mock import MagicMock, patch

import pytest


def test_client_default_url():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient()
    assert client.base_url == "http://localhost:1933"


def test_client_custom_url():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient(base_url="http://10.0.0.1:1933")
    assert client.base_url == "http://10.0.0.1:1933"


def test_client_is_available_true():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient()
    with patch.object(client, '_get', return_value={"status": "ok"}):
        assert client.is_available() is True


def test_client_is_available_false_on_connection_error():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient()
    with patch.object(client, '_get', side_effect=ConnectionError("refused")):
        assert client.is_available() is False
