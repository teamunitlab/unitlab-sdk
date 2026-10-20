"""Local Agent receiver: verify the webhook, then read, save and complete its task.

Environment: UNITLAB_AGENT_WEBHOOK_SECRET (the Agent stage's signing secret),
UNITLAB_API_KEY and optionally UNITLAB_API_URL (a workspace API key and its API).
Expose port 8091 with ``cloudflared tunnel --url http://127.0.0.1:8091`` and put
that HTTPS address in the Agent stage. ``transform`` returns None (no change),
so nothing is saved; replace it with your model.
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from unitlab import AgentWebhook, TaskAnnotation, UnitlabClient, UnitlabError


def transform(item: TaskAnnotation) -> dict | None:
    """Replace with your model: return the item's new UUEF document, or None.

    ``item.document`` is the item's UUEF (``item.result`` for a lidar scene,
    whose ``item.format`` is "native"); ``item.source_url`` is a signed media
    URL (never log it). None means "no change": a save always writes a new
    version credited to the API key's creator, even for an identical document.
    """
    return None


def main() -> None:
    secret = os.environ["UNITLAB_AGENT_WEBHOOK_SECRET"]
    client = UnitlabClient()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    self.send_error(413)
                    return
                event = AgentWebhook.verify(
                    self.rfile.read(length), self.headers, secret
                )
            except ValueError:
                self.send_error(400, "Invalid Agent webhook")
                return
            if event.is_test:  # "Test connection" button: acknowledge only.
                self.send_response(204)
                self.end_headers()
                return
            ref = event.task  # one task per event
            try:
                task = client.get_workflow_task(ref.task_id)
                for item in task.get_annotations():
                    document = transform(item)
                    if document is not None:
                        # Replaces the item whole; objects left out are deleted.
                        task.save_annotations(item, document)
                task.complete_agent(ref.run_id)
                # On a model error: task.fail_agent(ref.run_id, "what went wrong")
            except UnitlabError:
                self.send_error(503, "Unitlab call failed; retry delivery")
                return
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            # Do not put signing secrets, API keys, signed URLs or payloads in logs.
            pass

    # shortcut: synchronous local smoke only; enqueue durably before 2xx for long jobs.
    with ThreadingHTTPServer(("127.0.0.1", 8091), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
