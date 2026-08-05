import asyncio
from contextlib import contextmanager

import httpx
import pytest

from unitlab import NetworkError
from unitlab._downloader import download_annotation, download_files


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"partial"
        raise httpx.ReadError("connection lost")


def test_annotation_download_uses_destination_and_long_manifest_timeout(
    monkeypatch,
    tmp_path,
):
    posts = []
    streams = []
    file_url = "https://files.test/release-train.zip?signature=temporary"

    class Api:
        @staticmethod
        def post(*args, **kwargs):
            posts.append((args, kwargs))
            return {"file": file_url}

    response = httpx.Response(
        200,
        content=b"archive",
        request=httpx.Request("GET", file_url),
    )

    @contextmanager
    def stream(*args, **kwargs):
        streams.append((args, kwargs))
        yield response

    monkeypatch.setattr(
        "unitlab._downloader.httpx.stream",
        stream,
    )
    destination = tmp_path / "annotations"

    result = download_annotation(Api(), "release-1", "train", destination)

    final = destination / "release-train.zip"
    assert result == str(final.resolve())
    assert final.read_bytes() == b"archive"
    assert not (destination / "release-train.zip.part").exists()
    assert streams == [(("GET", file_url), {"timeout": 300.0})]
    assert posts == [
        (
            ("/api/sdk/releases/release-1/",),
            {
                "json": {
                    "download_type": "annotation",
                    "split_type": "train",
                },
                "timeout": 600.0,
            },
        )
    ]


def test_failed_download_does_not_leave_a_file_that_next_run_skips(
    monkeypatch,
    tmp_path,
):
    posts = []

    class Api:
        @staticmethod
        def post(*args, **kwargs):
            posts.append((args, kwargs))
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
    assert all(kwargs["timeout"] == 600.0 for _args, kwargs in posts)


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


def test_download_files_preserves_server_group_and_collision_paths(tmp_path):
    class Api:
        @staticmethod
        def post(*_args, **_kwargs):
            return [
                {
                    "file_name": "group-1/front/scan.txt",
                    "content": "front",
                },
                {
                    "file_name": "row-a/duplicate.txt",
                    "content": "a",
                },
                {
                    "file_name": "row-b/duplicate.txt",
                    "content": "b",
                },
            ]

    destination = tmp_path / "release"

    download_files(Api(), "release-1", destination)

    assert (destination / "group-1" / "front" / "scan.txt").read_text() == "front"
    assert (destination / "row-a" / "duplicate.txt").read_text() == "a"
    assert (destination / "row-b" / "duplicate.txt").read_text() == "b"
