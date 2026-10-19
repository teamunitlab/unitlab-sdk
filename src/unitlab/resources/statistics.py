from __future__ import annotations

from datetime import date
from typing import Any

from ._base import Namespace, identifier


def _period(date_from, date_to) -> dict[str, str]:
    if (date_from is None) != (date_to is None):
        raise ValueError("date_from and date_to must be given together.")
    if date_from is None:
        return {}
    return {
        "from": date_from.isoformat() if isinstance(date_from, date) else str(date_from),
        "to": date_to.isoformat() if isinstance(date_to, date) else str(date_to),
    }


def _ids(values) -> str | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
        values = [values]
    return ",".join(identifier(value) for value in values)


class StatisticsNamespace(Namespace):
    """The numbers of the statistics pages, read with the API key's creator.

    A key reads what its creator reads in the web app: the team's numbers with
    the ``view_team_statistics`` permission, otherwise the creator's own.
    Every response carries ``as_of``, ``tz`` and ``period``; each metric is
    ``{"value", "numerator", "denominator", "unit"}`` and ``value`` is None
    when there is no data.
    """

    def catalog(self) -> list[dict[str, Any]]:
        """Every metric with its key, unit and definition."""
        return self._api.get("/api/sdk/statistics/catalog/")["metrics"]

    def overview(
        self,
        *,
        projects=None,
        members=None,
        date_from=None,
        date_to=None,
        tz: str = "UTC",
        scope: str | None = None,
        compare: bool = False,
    ) -> dict[str, Any]:
        """Every metric for a scope and period (30 days by default).

        Args:
            projects: Project ids or objects; empty means every visible project.
            members: Member ids (team scope only).
            date_from: First day, a ``date`` or ``YYYY-MM-DD``; with ``date_to``.
            date_to: Last day, included.
            tz: IANA time zone that cuts the days.
            scope: ``"own"`` for the creator's own numbers.
            compare: Also return the previous period of the same length.
        """
        return self._api.get(
            "/api/sdk/statistics/overview/",
            params=self._params(projects, members, date_from, date_to, tz, scope)
            | ({"compare": "true"} if compare else {}),
        )

    def trend(
        self,
        keys=None,
        *,
        projects=None,
        members=None,
        date_from=None,
        date_to=None,
        tz: str = "UTC",
        granularity: str = "day",
        scope: str | None = None,
    ) -> dict[str, Any]:
        """Zero-filled series per ``day``, ``week`` or ``month`` for some metrics."""
        params = self._params(projects, members, date_from, date_to, tz, scope)
        params["granularity"] = granularity
        if keys:
            params["keys"] = ",".join(keys)
        return self._api.get("/api/sdk/statistics/trend/", params=params)

    def people(self, *, sort: str = "submissions", descending: bool = True, **filters):
        """One row per member; pages through every row."""
        return self._rows("/api/sdk/statistics/people/", sort, descending, filters)

    def projects(self, *, sort: str = "items_completed", descending: bool = True, **filters):
        """One row per project; pages through every row."""
        return self._rows("/api/sdk/statistics/projects/", sort, descending, filters)

    def me(self, *, date_from=None, date_to=None, tz: str = "UTC") -> dict[str, Any]:
        """The key creator's own numbers, with the previous period."""
        return self._api.get(
            "/api/sdk/statistics/me/", params=_period(date_from, date_to) | {"tz": tz}
        )

    def _params(self, projects, members, date_from, date_to, tz, scope):
        params: dict[str, Any] = {"tz": tz, **_period(date_from, date_to)}
        if _ids(projects):
            params["project_ids"] = _ids(projects)
        if _ids(members):
            params["member_ids"] = _ids(members)
        if scope:
            params["scope"] = scope
        return params

    def _rows(self, endpoint, sort, descending, filters):
        params = self._params(
            filters.get("projects"),
            filters.get("members"),
            filters.get("date_from"),
            filters.get("date_to"),
            filters.get("tz", "UTC"),
            filters.get("scope"),
        )
        params.update(sort=sort, direction="desc" if descending else "asc", limit=200)
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = self._api.get(endpoint, params={**params, "offset": offset})
            rows.extend(payload["results"])
            offset += len(payload["results"])
            if not payload["results"] or offset >= payload["count"]:
                return rows
