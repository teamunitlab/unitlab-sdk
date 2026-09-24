import httpx
import pytest

from unitlab import (
    ConflictError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
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
