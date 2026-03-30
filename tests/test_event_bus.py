from __future__ import annotations

import asyncio

import pytest

from src.bus.event_bus import Event, EventBus


@pytest.fixture()
def bus() -> EventBus:
    return EventBus()


class TestEventBus:
    @pytest.mark.asyncio
    async def test_emit_calls_listener(self, bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.on("test.event", handler)
        await bus.emit(Event(type="test.event", session_id="s1"))
        assert len(received) == 1
        assert received[0].session_id == "s1"

    @pytest.mark.asyncio
    async def test_no_listeners_is_noop(self, bus: EventBus) -> None:
        await bus.emit(Event(type="unhandled", session_id="s1"))

    @pytest.mark.asyncio
    async def test_multiple_listeners(self, bus: EventBus) -> None:
        calls: list[str] = []

        async def a(event: Event) -> None:
            calls.append("a")

        async def b(event: Event) -> None:
            calls.append("b")

        bus.on("x", a)
        bus.on("x", b)
        await bus.emit(Event(type="x", session_id="s1"))
        assert calls == ["a", "b"]

    @pytest.mark.asyncio
    async def test_off_removes_listener(self, bus: EventBus) -> None:
        calls: list[str] = []

        async def handler(event: Event) -> None:
            calls.append("called")

        bus.on("x", handler)
        bus.off("x", handler)
        await bus.emit(Event(type="x", session_id="s1"))
        assert calls == []

    @pytest.mark.asyncio
    async def test_listener_error_does_not_break_others(self, bus: EventBus) -> None:
        calls: list[str] = []

        async def bad(event: Event) -> None:
            raise RuntimeError("boom")

        async def good(event: Event) -> None:
            calls.append("ok")

        bus.on("x", bad)
        bus.on("x", good)
        await bus.emit(Event(type="x", session_id="s1"))
        assert calls == ["ok"]

    def test_listener_count(self, bus: EventBus) -> None:
        async def noop(event: Event) -> None:
            pass

        assert bus.listener_count == 0
        bus.on("a", noop)
        bus.on("b", noop)
        assert bus.listener_count == 2

    @pytest.mark.asyncio
    async def test_event_payload(self, bus: EventBus) -> None:
        received: list[dict] = []

        async def handler(event: Event) -> None:
            received.append(event.payload)

        bus.on("msg", handler)
        await bus.emit(Event(type="msg", session_id="s1", payload={"text": "hello"}))
        assert received[0]["text"] == "hello"
