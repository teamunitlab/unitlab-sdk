from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
import tqdm

from ._http import _safe_path
from ._uploader import run_sync
from .exceptions import NetworkError

DOWNLOAD_CONCURRENCY = 50


def download_annotation(api, release_id: str, split: str | None = None) -> str:
    payload = {"download_type": "annotation"}
    if split is not None:
        payload["split_type"] = split
    response = api.post(f"/api/sdk/releases/{release_id}/", json=payload)
    file_url = response["file"]
    filename = os.path.basename(urlparse(file_url).path) or f"{release_id}.zip"
    partial = f"{filename}.part"
    try:
        with httpx.stream("GET", file_url, timeout=300.0) as stream:
            stream.raise_for_status()
            with open(partial, "wb") as handle:
                for chunk in stream.iter_bytes():
                    handle.write(chunk)
        os.replace(partial, filename)
    except (httpx.HTTPError, OSError) as exc:
        if os.path.exists(partial):
            os.remove(partial)
        raise NetworkError(f"Failed to download release: {exc}", exc) from exc
    return os.path.abspath(filename)


def download_files(api, release_id: str, dest: str | Path | None = None) -> str:
    response = api.post(
        f"/api/sdk/releases/{release_id}/",
        json={"download_type": "files"},
    )
    base_folder = str(Path(dest) if dest is not None else Path(release_id))
    os.makedirs(base_folder, exist_ok=True)
    pending = []
    for item in response:
        file_name = item["file_name"]
        file_path = _safe_path(base_folder, file_name)
        os.makedirs(os.path.dirname(file_path) or base_folder, exist_ok=True)
        if "content" in item:
            if not os.path.isfile(file_path):
                with open(file_path, "w", encoding="utf-8") as handle:
                    handle.write(item["content"])
        elif "source" in item and not os.path.isfile(file_path):
            pending.append((file_name, item["source"], file_path))
    if not pending:
        return base_folder

    async def run() -> None:
        semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
        failures = []

        async def one(client, file_name, source, file_path):
            async with semaphore:
                partial = f"{file_path}.part"
                try:
                    async with client.stream("GET", source) as stream:
                        stream.raise_for_status()
                        with open(partial, "wb") as handle:
                            async for chunk in stream.aiter_bytes():
                                handle.write(chunk)
                    os.replace(partial, file_path)
                except Exception as exc:
                    if os.path.exists(partial):
                        os.remove(partial)
                    failures.append((file_name, str(exc)))

        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            with tqdm.tqdm(total=len(pending), ncols=80, disable=None) as progress:
                tasks = [one(client, *item) for item in pending]
                for task in asyncio.as_completed(tasks):
                    await task
                    progress.update(1)
        if failures:
            summary = "; ".join(f"{name}: {error}" for name, error in failures[:5])
            raise NetworkError(
                f"Failed to download {len(failures)} of {len(pending)} files. {summary}"
            )

    run_sync(run())
    return base_folder
