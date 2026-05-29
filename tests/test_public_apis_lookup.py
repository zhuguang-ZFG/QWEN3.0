"""Tests for lookup public APIs (dictionary, WHOIS, QR, geocode)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_gateway import public_apis_lookup as lookup


class TestFetchQr:
    def test_builds_url(self):
        r = lookup.fetch_qr("https://lima.test")
        assert r["ok"]
        assert "qrserver.com" in r["text"]
        assert "https://lima.test" in r["text"]

    def test_requires_payload(self):
        assert not lookup.fetch_qr("")["ok"]


class TestFetchDictionary:
    def test_mocked(self, monkeypatch):
        monkeypatch.setattr(
            lookup,
            "_get_json",
            lambda url, **kw: [
                {
                    "word": "hello",
                    "meanings": [
                        {
                            "partOfSpeech": "noun",
                            "definitions": [{"definition": "a greeting"}],
                        }
                    ],
                }
            ],
        )
        r = lookup.fetch_dictionary("hello")
        assert r["ok"]
        assert "greeting" in r["text"]


class TestFetchWhois:
    def test_invalid_domain(self):
        assert not lookup.fetch_whois("not a domain")["ok"]

    def test_mocked(self, monkeypatch):
        monkeypatch.setattr(
            lookup,
            "_get_json",
            lambda url, **kw: {
                "status": ["active"],
                "events": [{"eventAction": "registration", "eventDate": "2000-01-01"}],
                "entities": [],
            },
        )
        r = lookup.fetch_whois("example.com")
        assert r["ok"]
        assert "example.com" in r["text"]


class TestFetchImage:
    def test_returns_picsum_url(self):
        r = lookup.fetch_image("cat")
        assert r["ok"]
        assert "picsum.photos" in r["text"]


class TestFetchRegex:
    def test_match(self):
        r = lookup.fetch_regex_test(r"\d+ order42")
        assert r["ok"]
        assert "42" in r["text"]

    def test_invalid_pattern(self):
        assert not lookup.fetch_regex_test("[unclosed text")["ok"]


class TestFetchSsl:
    def test_invalid_host(self):
        assert not lookup.fetch_ssl("not valid host!")["ok"]


class TestFetchRandomuser:
    def test_mocked(self, monkeypatch):
        monkeypatch.setattr(
            lookup,
            "_get_json",
            lambda url, **kw: {
                "results": [
                    {
                        "name": {"title": "Mr", "first": "John", "last": "Doe"},
                        "location": {"city": "Austin", "country": "United States"},
                        "email": "john@example.com",
                        "phone": "555-0100",
                    }
                ]
            },
        )
        r = lookup.fetch_randomuser("demo")
        assert r["ok"]
        assert "John" in r["text"]
        assert "demo" in r["text"]


class TestFetchUuid:
    def test_single(self):
        r = lookup.fetch_uuid("")
        assert r["ok"]
        assert "UUID" in r["text"]

    def test_count_capped(self):
        r = lookup.fetch_uuid("3")
        assert r["ok"]
        assert r["text"].count("-") >= 3 * 4  # three uuid v4 strings


class TestFetchGeocode:
    def test_mocked(self, monkeypatch):
        monkeypatch.setattr(
            lookup,
            "_get_json",
            lambda url, **kw: [
                {"display_name": "Beijing", "lat": "39.9", "lon": "116.4"},
            ],
        )
        r = lookup.fetch_geocode("北京")
        assert r["ok"]
        assert "39.9" in r["text"]
