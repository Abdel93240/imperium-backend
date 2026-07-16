"""Importable handlers for runner lock tests (resolved via handler_ref)."""

import threading
import time

# Test hooks (set by tests before launching jobs).
release_event = threading.Event()
started_event = threading.Event()
calls: list[str] = []


def ok(ctx, window) -> None:
    calls.append("ok")
    ctx.items_in = 3
    ctx.items_out = 3
    ctx.detail = {"handled": True}


def blocking(ctx, window) -> None:
    started_event.set()
    release_event.wait(timeout=10)


def failing(ctx, window) -> None:
    raise RuntimeError("handler boom")


def sleepy(ctx, window) -> None:
    time.sleep(5)


def gpu_down(ctx, window) -> None:
    from app.services.ai.embedding import GpuServiceUnreachable

    raise GpuServiceUnreachable("embedding serving down")


def advance_cursor(ctx, window) -> None:
    ctx.cursor_ts = window.to_ts
