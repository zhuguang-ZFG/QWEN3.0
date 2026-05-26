import router_http
import smart_router
from router_circuit_breaker import reset_for_tests


def setup_function():
    reset_for_tests()


def _image_messages():
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,abc"},
                },
            ],
        }
    ]


def test_has_vision_content_delegates_to_detect_vision_request():
    assert smart_router._has_vision_content(_image_messages()) is True
    assert smart_router._has_vision_content(
        [{"role": "user", "content": "plain text"}]
    ) is False


def test_call_api_routes_cf_vision_with_image_content(monkeypatch):
    def unexpected_urlopen(*_args, **_kwargs):
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(router_http, "cb_allow", lambda _name: True)
    monkeypatch.setattr(router_http, "cb_record", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(router_http.urllib.request, "urlopen", unexpected_urlopen)
    monkeypatch.setitem(
        router_http.BACKENDS,
        "cf_vision",
        {
            "key": "test",
            "auth": "bearer",
            "fmt": "openai",
            "url": "https://example.test",
            "model": "vision",
        },
    )
    monkeypatch.setattr(
        router_http,
        "_call_cf_vision",
        lambda _msgs, _mt, _t0: "vision-ok",
    )

    assert smart_router.call_api("cf_vision", _image_messages()) == "vision-ok"
