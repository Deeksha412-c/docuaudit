import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "frontend"))

import pytest
import requests

from api_client import Api, ApiError, Unauthorized


class Resp:
    def __init__(self, status=200, data=None, content=b""):
        self.status_code, self._data, self.content = status, data, content

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


def patch(monkeypatch, response=None, error=None):
    calls = []

    def fake(method, url, headers=None, timeout=None, **kwargs):
        calls.append({"method": method, "url": url, "headers": headers or {}, **kwargs})
        if error:
            raise error
        return response

    monkeypatch.setattr(requests, "request", fake)
    return calls


def test_the_token_is_sent_as_a_bearer_header(monkeypatch):
    calls = patch(monkeypatch, Resp(200, []))
    Api("http://api", "abc123").documents()
    assert calls[0]["headers"]["Authorization"] == "Bearer abc123"
    assert calls[0]["url"] == "http://api/documents"


def test_no_token_means_no_header(monkeypatch):
    calls = patch(monkeypatch, Resp(200, {"access_token": "t"}))
    Api("http://api").login("a@b.com", "pw")
    assert "Authorization" not in calls[0]["headers"]
    assert calls[0]["data"] == {"username": "a@b.com", "password": "pw"}     # the login endpoint takes a form


def test_an_expired_session_is_reported_separately(monkeypatch):
    patch(monkeypatch, Resp(401, {"detail": "Your session is not valid."}))
    with pytest.raises(Unauthorized):
        Api("http://api", "old-token").documents()


def test_a_wrong_password_is_an_ordinary_error_with_the_servers_message(monkeypatch):
    patch(monkeypatch, Resp(401, {"detail": "Incorrect email or password."}))
    with pytest.raises(ApiError) as caught:
        Api("http://api").login("a@b.com", "wrong")
    assert not isinstance(caught.value, Unauthorized)
    assert caught.value.message == "Incorrect email or password."


def test_validation_errors_are_shown_as_one_message(monkeypatch):
    patch(monkeypatch, Resp(422, {"detail": [{"msg": "Field required"}]}))
    with pytest.raises(ApiError) as caught:
        Api("http://api").signup("a@b.com", "pw")
    assert caught.value.message == "Field required"


def test_an_unreachable_api_gives_a_friendly_message(monkeypatch):
    patch(monkeypatch, error=requests.exceptions.ConnectionError("refused"))
    with pytest.raises(ApiError) as caught:
        Api("http://api", "t").documents()
    assert "Could not reach the API" in caught.value.message


def test_a_downloaded_file_is_returned_as_bytes(monkeypatch):
    patch(monkeypatch, Resp(200, None, b"%PDF-1.4"))
    assert Api("http://api", "t").file("doc-1") == b"%PDF-1.4"
