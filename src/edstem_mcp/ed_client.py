"""Thin HTTP client over the (unofficial) Ed Discussion API.

Endpoints are reverse-engineered; see https://github.com/smartspot2/edapi for the
source of truth on paths. The Ed API is in beta and may change without notice.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://us.edstem.org/api/"


class EdError(RuntimeError):
    """Raised when an Ed API request fails."""


class EdClient:
    """Minimal authenticated client for the Ed Discussion API."""

    def __init__(
        self,
        token: str | None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        """Configure the HTTP client and validate that a token is present."""
        if not token:
            raise EdError(
                "Missing Ed API token. Set ED_API_TOKEN "
                "(create one at https://edstem.org/us/settings/api-tokens)."
            )
        # httpx joins relative paths against base_url; the trailing slash matters.
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # -- internal ---------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Issue an authenticated GET and return the parsed JSON body."""
        try:
            resp = self._client.get(path, params=params)
        except httpx.HTTPError as exc:  # network/timeout errors
            raise EdError(f"Network error calling Ed API ({path}): {exc}") from exc

        if resp.status_code == 401:
            raise EdError(
                "Ed API returned 401 Unauthorized — check that ED_API_TOKEN is valid "
                "and that you are using the right region (US vs EU) base URL."
            )
        if resp.status_code >= 400:
            raise EdError(
                f"Ed API error {resp.status_code} for {path}: {resp.text[:500]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise EdError(f"Ed API returned non-JSON for {path}: {resp.text[:200]}") from exc

    # -- user / courses ---------------------------------------------------

    def get_user(self) -> dict[str, Any]:
        """GET /user — user info plus the list of courses the user belongs to."""
        return self._get("user")

    def list_courses(self) -> list[dict[str, Any]]:
        """Return a normalized list of the user's courses.

        The /user payload nests each course under a ``course`` key alongside the
        user's ``role`` in that course.
        """
        data = self.get_user()
        courses: list[dict[str, Any]] = []
        for entry in data.get("courses", []):
            course = entry.get("course", entry)
            courses.append(
                {
                    "id": course.get("id"),
                    "code": course.get("code"),
                    "name": course.get("name"),
                    "year": course.get("year"),
                    "session": course.get("session"),
                    "role": entry.get("role"),
                }
            )
        return courses

    # -- threads ----------------------------------------------------------

    def search_threads(
        self,
        course_id: int,
        query: str,
        limit: int = 30,
        offset: int = 0,
        sort: str = "new",
    ) -> list[dict[str, Any]]:
        """Keyword-search threads in a course (Ed's web search uses ``keyword``)."""
        data = self._get(
            f"courses/{course_id}/threads",
            params={
                "limit": limit,
                "offset": offset,
                "sort": sort,
                "keyword": query,
            },
        )
        return data.get("threads", [])

    def list_threads(
        self,
        course_id: int,
        limit: int = 30,
        offset: int = 0,
        sort: str = "new",
    ) -> list[dict[str, Any]]:
        """List recent threads in a course (no keyword filter)."""
        data = self._get(
            f"courses/{course_id}/threads",
            params={"limit": limit, "offset": offset, "sort": sort},
        )
        return data.get("threads", [])

    def get_thread(self, thread_id: int) -> dict[str, Any]:
        """GET /threads/{id} — full thread with answers and comments."""
        data = self._get(f"threads/{thread_id}")
        return data.get("thread", data)
