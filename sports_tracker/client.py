"""Thin HTTP layer with timeouts, retries and consistent error handling."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sports_tracker import __version__

DEFAULT_TIMEOUT = 10.0
USER_AGENT = f"sports-tracker/{__version__}"


class ApiError(RuntimeError):
    """Raised when an upstream API cannot be reached or returns bad data."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpClient:
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = 2,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or self._build_session(retries)

    @staticmethod
    def _build_session(retries: int) -> requests.Session:
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ApiError(f"Could not reach {url}: {exc.__class__.__name__}") from exc

        if response.status_code == 404:
            raise ApiError("No data is available for this request (404).", 404)
        if not response.ok:
            raise ApiError(
                f"Request failed with status {response.status_code}.", response.status_code
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ApiError("The server returned a response that was not valid JSON.") from exc
