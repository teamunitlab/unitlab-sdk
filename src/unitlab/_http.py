from __future__ import annotations

import os
from typing import Any

import httpx

from .exceptions import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    RequestTimeoutError,
    SubscriptionError,
    ValidationError,
)


def _extract_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        for key in ("detail", "message"):
            if key in body:
                return str(body[key])
        parts = []
        for field, errors in body.items():
            if isinstance(errors, list):
                value = ", ".join(str(error) for error in errors)
            else:
                value = str(errors)
            parts.append(f"{field}: {value}")
        if parts:
            return "; ".join(parts)
    return str(body)


def _extract_error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        return str(body.get("code") or "")
    return ""


def raise_for_response(response: httpx.Response) -> None:
    if response.is_success:
        return
    message = _extract_error_message(response)
    code = _extract_error_code(response)
    error = httpx.HTTPStatusError(
        message,
        request=response.request,
        response=response,
    )
    if response.status_code == 400:
        raise ValidationError(message, error, code)
    if response.status_code == 401:
        raise AuthenticationError(message or "Authentication failed", error, code)
    if response.status_code == 403:
        if code == "permission_denied":
            raise PermissionDeniedError(message or "Forbidden", error, code)
        raise SubscriptionError(message or "Forbidden", error, code)
    if response.status_code == 404 or "not found" in message.lower():
        raise NotFoundError(message, error, code)
    raise NetworkError(message, error, code)


def _safe_path(base: str, untrusted: str) -> str:
    base = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base, untrusted))
    if not target.startswith(base + os.sep) and target != base:
        raise ValueError(f"Path traversal detected: {untrusted!r}")
    return target


class HttpApi:
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url
        self.client = httpx.Client(
            base_url=api_url,
            headers={"Authorization": f"Api-Key {api_key}"},
            transport=httpx.HTTPTransport(retries=3),
            timeout=60.0,
        )

    def close(self) -> None:
        self.client.close()

    def async_client(self, *, timeout: float = 600.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"Api-Key {self.api_key}"},
            timeout=timeout,
        )

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: Any = None,
        files: Any = None,
        timeout: float | None = None,
    ) -> Any:
        try:
            kwargs = {
                "params": params,
                "json": json,
                "data": data,
                "files": files,
            }
            if timeout is not None:
                kwargs["timeout"] = timeout
            response = self.client.request(method, endpoint, **kwargs)
        except httpx.TimeoutException as exc:
            raise RequestTimeoutError(str(exc), exc) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(str(exc), exc) from exc
        raise_for_response(response)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise NetworkError("Unexpected response format", exc) from exc

    def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        return self.request("GET", endpoint, params=params, timeout=timeout)

    def post(
        self,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        data: Any = None,
        files: Any = None,
        timeout: float | None = None,
    ) -> Any:
        return self.request(
            "POST",
            endpoint,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
        )
