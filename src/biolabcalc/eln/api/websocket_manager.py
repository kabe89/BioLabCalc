"""
Module: biolabcalc.eln.api.websocket_manager
Component: Real-Time Concurrency & WebSocket Connection Manager
Architectural Role: Core concurrency module managing real-time WebSocket client connections,
topic-based subscription routing, and asynchronous broadcasting of live kinetic countdown timers,
collaborative lab notebook edits, and freezer grid slot occupancy changes.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("biolabcalc.eln.websocket")


class WebSocketConnection:
    """
    Client connection representation supporting bidirectional asynchronous transmission
    and event queue buffering.

    Architectural Role: Wraps physical ASGI WebSocket socket or memory event buffer.
    """

    def __init__(self, client_id: str, websocket: Optional[Any] = None) -> None:
        """
        Initialize connection instance.

        Parameter client_id (str): Unique client session identifier.
        Parameter websocket (Optional[Any]): Underlying ASGI WebSocket instance.
        """
        self.client_id = client_id
        self.websocket = websocket
        self.subscribed_topics: Set[str] = set()
        self.connected_at = datetime.now(timezone.utc).isoformat()
        self.buffered_messages: collections.deque[Dict[str, Any]] = collections.deque(maxlen=100)

    async def send_json(self, data: Dict[str, Any]) -> None:
        """
        Transmit JSON payload to connected client, falling back to buffer if disconnected.

        Parameter data (Dict[str, Any]): Outbound payload.
        """
        if self.websocket is not None:
            try:
                if hasattr(self.websocket, "send_json"):
                    await self.websocket.send_json(data)
                elif hasattr(self.websocket, "send_text"):
                    await self.websocket.send_text(json.dumps(data))
                return
            except Exception as e:
                logger.warning(f"Failed to transmit to WebSocket {self.client_id}: {e}")

        # Buffer message in memory for polling retrieval
        self.buffered_messages.append(data)


class WebSocketManager:
    """
    Topic-based real-time connection broker for lab notebook collaboration and kinetic timers.

    Architectural Role: Governs pub/sub channels (e.g. 'timers', 'notebook:{id}', 'inventory:{id}'),
    client connection lifecycle, and asynchronous multi-cast broadcasting.
    """

    def __init__(self) -> None:
        """
        Initialize WebSocketManager with topic registries and thread lock.

        """
        self._lock = threading.Lock()
        self._connections: Dict[str, WebSocketConnection] = {}
        self._topic_subscribers: Dict[str, Set[str]] = {}
        self._topic_event_log: Dict[str, List[Dict[str, Any]]] = {}

    def connect(self, client_id: str, websocket: Optional[Any] = None) -> WebSocketConnection:
        """
        Register a new client connection.

        Parameter client_id (str): Unique connection ID.
        Parameter websocket (Optional[Any]): ASGI WebSocket instance.
        Return Type: WebSocketConnection
        """
        with self._lock:
            conn = WebSocketConnection(client_id=client_id, websocket=websocket)
            self._connections[client_id] = conn
            logger.info(f"Client '{client_id}' connected to WebSocket manager.")
            return conn

    def disconnect(self, client_id: str) -> None:
        """
        Unregister client connection and purge from all subscribed topics.

        Parameter client_id (str): Client ID to disconnect.
        """
        with self._lock:
            conn = self._connections.pop(client_id, None)
            if conn:
                for topic in conn.subscribed_topics:
                    if topic in self._topic_subscribers:
                        self._topic_subscribers[topic].discard(client_id)
                        if len(self._topic_subscribers[topic]) == 0:
                            del self._topic_subscribers[topic]
            logger.info(f"Client '{client_id}' disconnected from WebSocket manager.")

    def subscribe(self, client_id: str, topic: str) -> bool:
        """
        Subscribe an active client to a specific topic channel.

        Parameter client_id (str): Client connection ID.
        Parameter topic (str): Topic channel (e.g. 'timers', 'notebook:ENTRY-1', 'inventory:BOX-1').
        Return Type: bool (True if subscribed, False if client not found).
        """
        with self._lock:
            conn = self._connections.get(client_id)
            if not conn:
                return False

            conn.subscribed_topics.add(topic)
            if topic not in self._topic_subscribers:
                self._topic_subscribers[topic] = set()
            self._topic_subscribers[topic].add(client_id)
            return True

    def unsubscribe(self, client_id: str, topic: str) -> None:
        """
        Unsubscribe client from a specific topic channel.

        Parameter client_id (str): Client connection ID.
        Parameter topic (str): Topic channel.
        """
        with self._lock:
            conn = self._connections.get(client_id)
            if conn:
                conn.subscribed_topics.discard(topic)
            if topic in self._topic_subscribers:
                self._topic_subscribers[topic].discard(client_id)

    async def broadcast(self, topic: str, message: Dict[str, Any], exclude_client: Optional[str] = None) -> int:
        """
        Broadcast JSON message asynchronously to all clients subscribed to topic.

        Parameter topic (str): Target topic channel.
        Parameter message (Dict[str, Any]): Outbound message payload.
        Parameter exclude_client (Optional[str]): Optional client ID to omit from broadcast (e.g. sender).
        Return Type: int (number of clients messaged).
        """
        envelope = {
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": message,
        }

        with self._lock:
            # Store in event log for polling fallback
            if topic not in self._topic_event_log:
                self._topic_event_log[topic] = []
            self._topic_event_log[topic].append(envelope)
            # Retain last 200 events per topic
            if len(self._topic_event_log[topic]) > 200:
                self._topic_event_log[topic].pop(0)

            subscribers = list(self._topic_subscribers.get(topic, set()))
            target_conns = [
                self._connections[cid]
                for cid in subscribers
                if cid in self._connections and (exclude_client is None or cid != exclude_client)
            ]

        for conn in target_conns:
            await conn.send_json(envelope)

        return len(target_conns)

    # -------------------------------------------------------------------------
    # DOMAIN-SPECIFIC BROADCAST HANDLERS
    # -------------------------------------------------------------------------

    async def broadcast_timer_countdown(self, timer_id: str, timer_data: Dict[str, Any]) -> int:
        """
        Broadcast live second-resolution kinetic countdown update to all subscribers on 'timers' channel.

        Parameter timer_id (str): Unique timer identifier.
        Parameter timer_data (Dict[str, Any]): Computed timer metrics (elapsed, remaining, status, deviation).
        Return Type: int
        """
        return await self.broadcast(
            topic="timers",
            message={"event": "TIMER_TICK", "timer_id": timer_id, "data": timer_data},
        )

    async def broadcast_notebook_edit(
        self,
        entry_id: str,
        edit_data: Dict[str, Any],
        sender_id: Optional[str] = None,
    ) -> int:
        """
        Broadcast real-time collaborative notebook field update or checkoff to co-workers.

        Parameter entry_id (str): Daily notebook entry ID.
        Parameter edit_data (Dict[str, Any]): Field delta or observation update.
        Parameter sender_id (Optional[str]): Client originating mutation to prevent echo.
        Return Type: int
        """
        return await self.broadcast(
            topic=f"notebook:{entry_id}",
            message={"event": "NOTEBOOK_EDIT", "entry_id": entry_id, "delta": edit_data},
            exclude_client=sender_id,
        )

    async def broadcast_inventory_update(self, box_id: str, change_data: Dict[str, Any]) -> int:
        """
        Broadcast freezer 2D box grid slot occupancy change or tube movement to connected lab workstations.

        Parameter box_id (str): Target storage box ID.
        Parameter change_data (Dict[str, Any]): Relocation, placement, or removal payload.
        Return Type: int
        """
        return await self.broadcast(
            topic=f"inventory:{box_id}",
            message={"event": "SLOT_UPDATE", "box_id": box_id, "change": change_data},
        )

    def poll_events(self, topic: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve recent broadcast events for clients operating in polling / non-WebSocket mode.

        Parameter topic (str): Channel to poll.
        Parameter limit (int): Maximum items to return.
        Return Type: List[Dict[str, Any]]
        """
        with self._lock:
            events = self._topic_event_log.get(topic, [])
            return list(events[-limit:])

    def get_connected_clients_count(self) -> int:
        """Return total active connections."""
        with self._lock:
            return len(self._connections)

    def clear_for_testing(self) -> None:
        """Reset internal connection state."""
        with self._lock:
            self._connections.clear()
            self._topic_subscribers.clear()
            self._topic_event_log.clear()


_global_ws_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """
    Get the process-level singleton instance of WebSocketManager.

    Return Type: WebSocketManager
    """
    return _global_ws_manager
