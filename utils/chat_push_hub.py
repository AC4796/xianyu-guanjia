"""浏览器端在线聊天推送中心（内存 + DB 持久化）。"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Set

from fastapi import WebSocket
from loguru import logger


class ChatPushHub:
    def __init__(self, max_memory_per_cookie: int = 200):
        self._lock = asyncio.Lock()
        self._user_sockets: Dict[int, Set[WebSocket]] = defaultdict(set)
        self._memory: Dict[str, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=max_memory_per_cookie)
        )
        self._buyer_avatar_cache: Dict[str, str] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._user_sockets[user_id].add(websocket)
        logger.info(f'聊天 WS 已连接 user_id={user_id}, 当前连接数={len(self._user_sockets[user_id])}')

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._user_sockets.get(user_id)
            if sockets and websocket in sockets:
                sockets.discard(websocket)
            if sockets is not None and not sockets:
                self._user_sockets.pop(user_id, None)
        logger.info(f'聊天 WS 已断开 user_id={user_id}')

    def cache_buyer_avatar(self, buyer_id: str, avatar_url: str) -> None:
        if buyer_id and avatar_url:
            self._buyer_avatar_cache[str(buyer_id)] = avatar_url

    def get_buyer_avatar(self, buyer_id: str) -> str:
        return self._buyer_avatar_cache.get(str(buyer_id), '')

    async def publish(self, owner_user_id: Optional[int], event: Dict[str, Any]) -> None:
        """写入内存并推送给所属后台用户。"""
        cookie_id = str(event.get('cookie_id') or '')
        if not cookie_id:
            return

        event = dict(event)
        event.setdefault('type', 'chat_message')
        event.setdefault('ts', int(time.time() * 1000))

        async with self._lock:
            self._memory[cookie_id].appendleft(event)
            targets = list(self._user_sockets.get(int(owner_user_id), set())) if owner_user_id is not None else []
            # 若未知归属，广播给所有已连接后台用户（单用户部署更稳妥）
            if not targets and owner_user_id is None:
                for socks in self._user_sockets.values():
                    targets.extend(list(socks))

        if not targets:
            return

        payload = json.dumps(event, ensure_ascii=False)
        dead: List[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        if dead and owner_user_id is not None:
            async with self._lock:
                for ws in dead:
                    self._user_sockets[int(owner_user_id)].discard(ws)

    def list_memory(self, cookie_ids: List[str], limit: int = 100) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for cid in cookie_ids:
            rows.extend(list(self._memory.get(cid, [])))
        rows.sort(key=lambda x: int(x.get('ts') or 0), reverse=True)
        return rows[:limit]

    def list_sessions_from_memory(self, cookie_ids: List[str]) -> List[Dict[str, Any]]:
        """按 cookie_id+chat_id 聚合最近一条。"""
        latest: Dict[str, Dict[str, Any]] = {}
        for cid in cookie_ids:
            for msg in self._memory.get(cid, []):
                chat_id = str(msg.get('chat_id') or '')
                if not chat_id:
                    continue
                key = f'{cid}:{chat_id}'
                if key not in latest or int(msg.get('ts') or 0) > int(latest[key].get('ts') or 0):
                    latest[key] = msg
        sessions = list(latest.values())
        sessions.sort(key=lambda x: int(x.get('ts') or 0), reverse=True)
        return sessions


chat_push_hub = ChatPushHub()
