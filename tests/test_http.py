import httpx
import pytest

from unitlab import (
    ConflictError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    RequestTimeoutError,
    SubscriptionError,
)
from unitlab._http import HttpApi, raise_for_response


def test_requests_keep_client_timeout_unless_explicitly_overridden():
    seen = []

    def handler(request):
        seen.append(request.extensions["timeout"])
        return httpx.Response(200, json={"ok": True})

    api = HttpApi("key", "http://testserver")
    api.client.close()
    api.client = httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(handler),
        timeout=12,
    )

    api.get("/default")
    api.get("/override", timeout=7)

    assert set(seen[0].values()) == {12}
    assert set(seen[1].values()) == {7}
    api.close()


def test_forbidden_responses_distinguish_permission_and_subscription_errors():
    request = httpx.Request("POST", "http://testserver/action")
    permission = httpx.Response(
        403,
        request=request,
        json={
            "detail": "A user-created API key is required.",
            "code": "permission_denied",
        },
    )
    subscription = httpx.Response(
        403,
        request=request,
        json={"detail": "Resource Limit Exceeded"},
    )

    with pytest.raises(PermissionDeniedError, match="user-created API key") as exc:
        raise_for_response(permission)
    assert exc.value.code == "permission_denied"

    with pytest.raises(SubscriptionError, match="Resource Limit Exceeded") as exc:
        raise_for_response(subscription)
    assert exc.value.code == ""


@pytest.mark.parametrize(
    "code",
    ["workspace_read_only", "workspace_license_required"],
)
def test_commercial_error_code_is_preserved(code):
    response = httpx.Response(
        403,
        request=httpx.Request("POST", "http://testserver/action"),
        json={
            "detail": "Workspace is read-only.",
            "code": code,
        },
    )

    with pytest.raises(SubscriptionError) as exc:
        raise_for_response(response)

    assert exc.value.code == code


def test_conflict_responses_raise_conflict_error_even_when_detail_says_not_found():
    # A 409 detail may legitimately contain "not found"; the message-based
    # NotFound fallback must never reclassify a conflict.
    response = httpx.Response(
        409,
        request=httpx.Request("POST", "http://testserver/action"),
        json={
            "detail": "Release 0.3 is still being prepared; archive not found yet.",
            "code": "release_not_ready",
        },
    )

    with pytest.raises(ConflictError, match="still being prepared") as exc:
        raise_for_response(response)

    assert isinstance(exc.value, NetworkError)
    assert not isinstance(exc.value, NotFoundError)
    assert exc.value.code == "release_not_ready"


@pytest.mark.parametrize(
    ("api_url", "expected_proxy"),
    [
        ("http://api.example.test", "http://http-proxy.test:8080"),
        ("https://api.example.test", "http://https-proxy.test:8081"),
        ("http://internal.example.test", None),
        ("https://internal.example.test", None),
    ],
)
def test_environment_proxies_and_no_proxy_route_requests(
    monkeypatch, api_url, expected_proxy
):
    # Observe the actual public transport selected by HTTPX, without opening
    # sockets or inspecting its private client/mount/pool attributes.
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://http-proxy.test:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://https-proxy.test:8081")
    monkeypatch.setenv("NO_PROXY", "internal.example.test")

    original_init = httpx.HTTPTransport.__init__
    transports = {}
    requests = []

    def initialize(transport, *args, **kwargs):
        transports[transport] = kwargs.get("proxy")
        original_init(transport, *args, **kwargs)

    def handle_request(transport, request):
        proxy = transports[transport]
        requests.append((request, proxy.url if proxy is not None else None))
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.HTTPTransport, "__init__", initialize)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)
    api = HttpApi("synthetic-key", api_url)
    try:
        assert api.get("/health") == {"ok": True}
    finally:
        api.close()

    assert len(requests) == 1
    request, proxy = requests[0]
    assert request.url == httpx.URL(api_url + "/health")
    assert proxy == (httpx.URL(expected_proxy) if expected_proxy else None)


@pytest.fixture
def http_api():
    api = HttpApi("synthetic-key", "https://api.example.test")
    yield api
    api.close()


@pytest.mark.parametrize(
    ("error_type", "sdk_error"),
    [(httpx.ConnectError, NetworkError), (httpx.ConnectTimeout, RequestTimeoutError)],
)
@pytest.mark.parametrize("failures", [3, 4])
def test_only_connection_failures_receive_three_retries(
    monkeypatch, http_api, error_type, sdk_error, failures
):
    attempts = []
    delays = []

    def request(method, endpoint, **kwargs):
        attempts.append((method, endpoint, kwargs))
        if len(attempts) <= failures:
            raise error_type("Connection could not be established")
        return httpx.Response(200, json={"created": True})

    monkeypatch.setattr(http_api.client, "request", request)
    monkeypatch.setattr("unitlab._http.time.sleep", delays.append)

    if failures == 3:
        assert http_api.post("/imports", json={"name": "fixture"}) == {"created": True}
    else:
        with pytest.raises(sdk_error) as exc:
            http_api.post("/imports", json={"name": "fixture"})
        assert isinstance(exc.value.detail, error_type)
    assert len(attempts) == 4
    assert delays == [0.0, 0.5, 1.0]
    assert all(
        method == "POST"
        and endpoint == "/imports"
        and kwargs["json"] == {"name": "fixture"}
        for method, endpoint, kwargs in attempts
    )


@pytest.mark.parametrize(
    ("error_type", "sdk_error"),
    [
        (httpx.ReadError, NetworkError),
        (httpx.WriteError, NetworkError),
        (httpx.ReadTimeout, RequestTimeoutError),
        (httpx.WriteTimeout, RequestTimeoutError),
        (httpx.PoolTimeout, RequestTimeoutError),
        (httpx.ProxyError, NetworkError),
        (httpx.RemoteProtocolError, NetworkError),
    ],
)
def test_post_is_not_retried_after_other_transport_failures(
    monkeypatch, http_api, error_type, sdk_error
):
    attempts = []
    delays = []

    def request(method, endpoint, **kwargs):
        attempts.append(method)
        raise error_type("Request failed")

    monkeypatch.setattr(http_api.client, "request", request)
    monkeypatch.setattr("unitlab._http.time.sleep", delays.append)
    with pytest.raises(sdk_error) as exc:
        http_api.post("/imports", json={"name": "fixture"})
    assert isinstance(exc.value.detail, error_type)
    assert attempts == ["POST"]
    assert delays == []


@pytest.mark.parametrize("status_code", [400, 409, 429, 503])
def test_post_error_status_is_not_retried(monkeypatch, http_api, status_code):
    attempts = []
    delays = []

    def request(method, endpoint, **kwargs):
        attempts.append(method)
        return httpx.Response(
            status_code,
            request=httpx.Request(method, "https://api.example.test" + endpoint),
            json={"detail": "Synthetic error"},
        )

    monkeypatch.setattr(http_api.client, "request", request)
    monkeypatch.setattr("unitlab._http.time.sleep", delays.append)
    with pytest.raises(NetworkError):
        http_api.post("/imports", json={"name": "fixture"})
    assert attempts == ["POST"]
    assert delays == []
