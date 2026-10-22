from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
import tqdm

from ._http import _safe_path, error_text
from ._uploader import run_sync
from .exceptions import NetworkError

DOWNLOAD_CONCURRENCY = 50


def download_annotation(
    api,
    release_id: str,
    split: str | None = None,
    dest: str | Path | None = None,
) -> str:
    payload = {"download_type": "annotation"}
    if split is not None:
        payload["split_type"] = split
    response = api.post(
        f"/api/sdk/releases/{release_id}/",
        json=payload,
        timeout=600.0,
    )
    file_url = response["file"]
    filename = os.path.basename(urlparse(file_url).path) or f"{release_id}.zip"
    destination = Path(dest) if dest is not None else Path()
    target = destination / filename
    partial = target.with_name(f"{target.name}.part")
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", file_url, timeout=300.0) as stream:
            stream.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in stream.iter_bytes():
                    handle.write(chunk)
        os.replace(partial, target)
    except (httpx.HTTPError, OSError) as exc:
        if partial.exists():
            partial.unlink()
        raise NetworkError(
            f"Failed to download release: {error_text(exc)}", exc
        ) from exc
    return str(target.resolve())


def download_files(api, release_id: str, dest: str | Path | None = None) -> str:
    response = api.post(
        f"/api/sdk/releases/{release_id}/",
        json={"download_type": "files"},
        timeout=600.0,
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
                # Through a `.part` file like the media below: an existing file
                # is skipped on the next run, so a write cut short must never
                # appear under the final name.
                partial = f"{file_path}.part"
                with open(partial, "w", encoding="utf-8") as handle:
                    handle.write(item["content"])
                os.replace(partial, file_path)
        elif "source" in item and not os.path.isfile(file_path):
            pending.append((file_name, item["source"], file_path))
    if not pending:
        return base_folder

    async def run() -> None:
        failures = []

        async def one(client, file_name, source, file_path):
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

        async def worker(client, queue, progress):
            for item in queue:
                await one(client, *item)
                progress.update(1)

        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            with tqdm.tqdm(total=len(pending), ncols=80, disable=None) as progress:
                # A fixed set of workers share one iterator, so only
                # DOWNLOAD_CONCURRENCY tasks exist however many files are
                # pending (one task per file held 100k tasks for 100k files).
                queue = iter(pending)
                workers = min(DOWNLOAD_CONCURRENCY, len(pending))
                await asyncio.gather(
                    *(worker(client, queue, progress) for _ in range(workers))
                )
        if failures:
            summary = "; ".join(f"{name}: {error}" for name, error in failures[:5])
            raise NetworkError(
                f"Failed to download {len(failures)} of {len(pending)} files. {summary}"
            )

    run_sync(run())
    return base_folder
