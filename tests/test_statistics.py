from datetime import date

import httpx
import pytest

from unitlab import UnitlabClient


def client_with_handler(handler):
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    client._api.client.close()
    client._api.client = httpx.Client(
        base_url="http://testserver",
        headers={"Authorization": "Api-Key key"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_overview_sends_period_projects_and_zone():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, json={"metrics": {"submissions": {"value": 3}}})

    client = client_with_handler(handler)
    result = client.statistics.overview(
        projects=["p1", "p2"],
        date_from=date(2026, 10, 1),
        date_to="2026-10-19",
        tz="Asia/Tashkent",
        compare=True,
    )

    assert result["metrics"]["submissions"]["value"] == 3
    url = seen[0]
    assert url.path == "/api/sdk/statistics/overview/"
    assert url.params["project_ids"] == "p1,p2"
    assert url.params["from"] == "2026-10-01"
    assert url.params["to"] == "2026-10-19"
    assert url.params["tz"] == "Asia/Tashkent"
    assert url.params["compare"] == "true"
    client.close()


def test_people_pages_through_every_row():
    pages = {
        "0": {"count": 3, "results": [{"member_id": "a"}, {"member_id": "b"}]},
        "2": {"count": 3, "results": [{"member_id": "c"}]},
    }

    def handler(request):
        assert request.url.path == "/api/sdk/statistics/people/"
        assert request.url.params["direction"] == "asc"
        return httpx.Response(200, json=pages[request.url.params["offset"]])

    client = client_with_handler(handler)
    rows = client.statistics.people(sort="name", descending=False)

    assert [row["member_id"] for row in rows] == ["a", "b", "c"]
    client.close()


def test_a_period_needs_both_dates():
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    with pytest.raises(ValueError, match="together"):
        client.statistics.overview(date_from="2026-10-01")
    client.close()
