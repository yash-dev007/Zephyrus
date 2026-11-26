"""Regression: SSE responses must never be gzip-compressed.

Starlette 0.41's GZipMiddleware compresses every response over minimum_size,
including ``text/event-stream``. Gzip buffers small writes until its internal
buffer fills, so an SSE client receives nothing until the stream ends — the UI
shows a spinner and then the whole reply appears at once. ``SSESafeGZipMiddleware``
marks SSE responses as already-encoded so each chunk is forwarded immediately,
while still gzipping normal bodies.
"""

import asyncio

from core.middleware import SSESafeGZipMiddleware


def _run(app, headers):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/stream",
        "headers": headers,
    }
    asyncio.run(app(scope, receive, send))
    return sent


def _headers(message):
    return {k.lower(): v for k, v in message["headers"]}


def test_sse_chunks_are_forwarded_uncompressed():
    async def inner(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/event-stream; charset=utf-8")],
        })
        for i in range(3):
            await send({
                "type": "http.response.body",
                "body": f"data: {i}\n\n".encode(),
                "more_body": True,
            })
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    app = SSESafeGZipMiddleware(inner, minimum_size=1)
    sent = _run(app, [(b"accept-encoding", b"gzip")])

    start = next(m for m in sent if m["type"] == "http.response.start")
    assert b"content-encoding" not in _headers(start)

    bodies = [
        m["body"] for m in sent
        if m["type"] == "http.response.body" and m.get("body")
    ]
    # Each event is forwarded as its own chunk, not buffered into one gzip blob.
    assert bodies == [b"data: 0\n\n", b"data: 1\n\n", b"data: 2\n\n"]


def test_large_non_sse_body_is_still_gzipped():
    async def inner(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b"x" * 4096,
            "more_body": False,
        })

    app = SSESafeGZipMiddleware(inner, minimum_size=1024)
    sent = _run(app, [(b"accept-encoding", b"gzip")])

    start = next(m for m in sent if m["type"] == "http.response.start")
    assert _headers(start).get(b"content-encoding") == b"gzip"
