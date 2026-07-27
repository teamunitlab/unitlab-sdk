from __future__ import annotations

import sys
import time
from collections.abc import Callable

import tqdm

from .exceptions import (
    NetworkError,
    NotFoundError,
    ProcessingTimeoutError,
    RequestTimeoutError,
    SubscriptionError,
)
from .types import ProcessingStatus

POLL_DELAYS = (1, 2, 4, 8, 10, 10, 10, 10, 20, 20)


def wait_for_processing(
    api,
    project_id: str,
    batch_queue_id: str,
    *,
    timeout: float = 1800,
    on_progress: Callable[[ProcessingStatus], None] | None = None,
    show_progress: bool = False,
) -> ProcessingStatus:
    show_progress = show_progress and sys.stderr.isatty()
    deadline = time.monotonic() + timeout
    transient_errors = 0
    last_status = None
    progress = None
    attempt = 0
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = api.get(
                    f"/api/sdk/projects/{project_id}/upload-sessions/"
                    f"{batch_queue_id}/status/",
                    timeout=remaining,
                )
                status = ProcessingStatus._from_raw(raw)
                last_status = status
                transient_errors = 0
                if on_progress:
                    on_progress(status)
                if show_progress:
                    if progress is None:
                        progress = tqdm.tqdm(total=status.total, ncols=80)
                    progress.total = status.total
                    progress.n = status.completed + status.failed
                    progress.refresh()
                if status.processing == 0:
                    return status
            except (NotFoundError, SubscriptionError):
                raise
            except (NetworkError, RequestTimeoutError):
                transient_errors += 1
                if transient_errors > 3:
                    raise

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            delay = POLL_DELAYS[min(attempt, len(POLL_DELAYS) - 1)]
            attempt += 1
            time.sleep(min(delay, remaining))
        raise ProcessingTimeoutError(
            f"Batch Queue {batch_queue_id} is still processing after "
            f"{timeout:g} seconds.",
            status=last_status,
        )
    finally:
        if progress is not None:
            progress.close()
