"""A thin client for the DocuAudit API. It adds the login token and turns failures into plain errors."""
import requests


class ApiError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.message = message
        self.status = status


class Unauthorized(ApiError):
    """The token is missing, expired or no longer valid."""


def _detail(response):
    try:
        detail = response.json().get("detail")
    except Exception:
        detail = None
    if isinstance(detail, list) and detail:                 # validation errors come as a list
        detail = detail[0].get("msg") if isinstance(detail[0], dict) else str(detail[0])
    return str(detail) if detail else f"The request failed ({response.status_code})."


class Api:
    def __init__(self, base_url, token=None, timeout=15):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method, path, timeout=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = requests.request(method, f"{self.base}{path}", headers=headers,
                                        timeout=timeout or self.timeout, **kwargs)
        except requests.exceptions.RequestException as error:
            raise ApiError("Could not reach the API. Is Docker running?") from error
        if response.status_code == 401 and self.token:
            raise Unauthorized("Your session has expired. Please sign in again.", 401)
        if response.status_code >= 400:
            raise ApiError(_detail(response), response.status_code)
        return response

    def signup(self, email, password, name=""):
        return self._request("POST", "/auth/signup", json={"email": email, "password": password, "name": name}).json()

    def login(self, email, password):
        return self._request("POST", "/auth/login", data={"username": email, "password": password}).json()

    def upload(self, name, data):
        files = {"file": (name, data, "application/pdf")}
        return self._request("POST", "/documents", files=files, timeout=60).json()

    def document(self, doc_id):
        return self._request("GET", f"/documents/{doc_id}").json()

    def documents(self):
        return self._request("GET", "/documents").json()

    def file(self, doc_id):
        return self._request("GET", f"/documents/{doc_id}/file").content
