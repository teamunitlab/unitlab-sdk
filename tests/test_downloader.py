import asyncio

import httpx
import pytest

from unitlab import NetworkError
from unitlab._downloader import download_files


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"partial"
        raise httpx.ReadError("connection lost")


def test_failed_download_does_not_leave_a_file_that_next_run_skips(
    monkeypatch,
    tmp_path,
):
    class Api:
        @staticmethod
        def post(*_args, **_kwargs):
            return [
                {
                    "file_name": "images/scan.png",
                    "source": "https://files.test/scan.png",
                }
            ]

    real_async_client = httpx.AsyncClient
    broken = True

    def handler(request):
        nonlocal broken
        if broken:
            broken = False
            return httpx.Response(200, stream=BrokenStream(), request=request)
        return httpx.Response(200, content=b"complete", request=request)

    def async_client(**kwargs):
        return real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    monkeypatch.setattr("unitlab._downloader.httpx.AsyncClient", async_client)
    destination = tmp_path / "release"

    with pytest.raises(NetworkError, match="Failed to download 1 of 1 files"):
        download_files(Api(), "release-1", destination)

    final = destination / "images" / "scan.png"
    partial = destination / "images" / "scan.png.part"
    assert not final.exists()
    assert not partial.exists()

    download_files(Api(), "release-1", destination)
    assert final.read_bytes() == b"complete"


def test_download_files_works_inside_a_running_event_loop(monkeypatch, tmp_path):
    class Api:
        @staticmethod
        def post(*_args, **_kwargs):
            return [
                {
                    "file_name": "scan.png",
                    "source": "https://files.test/scan.png",
                }
            ]

    real_async_client = httpx.AsyncClient

    def async_client(**kwargs):
        return real_async_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    content=b"complete",
                    request=request,
                )
            ),
            **kwargs,
        )

    monkeypatch.setattr("unitlab._downloader.httpx.AsyncClient", async_client)
    destination = tmp_path / "release"

    async def run():
        return download_files(Api(), "release-1", destination)

    assert asyncio.run(run()) == str(destination)
    assert (destination / "scan.png").read_bytes() == b"complete"
