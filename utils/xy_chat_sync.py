"""闲鱼 IM 会话同步：HTTP session.sync + 解析。"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List
from urllib.parse import unquote

import aiohttp
from loguru import logger

from utils.xianyu_utils import generate_sign, trans_cookies


def _pick(d: Any, *path: str, default: Any = '') -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def parse_session_item(item: Dict[str, Any]) -> Dict[str, Any]:
    session = item.get('session') or {}
    user_info = session.get('userInfo') or {}
    summary = _pick(item, 'message', 'summary', default={}) or {}
    if not isinstance(summary, dict):
        summary = {}

    avatar = (
        user_info.get('logo')
        or user_info.get('avatar')
        or user_info.get('headImg')
        or ''
    )
    session_id = str(session.get('sessionId') or '')
    # 去掉 @goofish 后缀
    if '@' in session_id:
        session_id = session_id.split('@', 1)[0]

    item_id = ''
    ext = session.get('extension') or session.get('ext') or {}
    if isinstance(ext, dict):
        item_id = str(ext.get('itemId') or ext.get('item_id') or '')
    if not item_id:
        item_id = str(_pick(item, 'message', 'extension', 'itemId', default='') or '')

    return {
        'chat_id': session_id,
        'buyer_id': str(user_info.get('userId') or user_info.get('uid') or ''),
        'buyer_nick': (
            user_info.get('nick')
            or user_info.get('fishNick')
            or user_info.get('displayName')
            or ''
        ),
        'buyer_avatar': avatar,
        'content': str(summary.get('summary') or summary.get('content') or ''),
        'item_id': item_id,
        'session_type': int(session.get('sessionType') or 0),
        'unread': int(summary.get('unread') or 0),
        'ts': int(summary.get('ts') or session.get('modifyTime') or 0),
    }


async def fetch_session_list(cookies_str: str, fetch_num: int = 50, timeout: float = 15.0) -> List[Dict[str, Any]]:
    """调用 mtop.taobao.idlemessage.pc.session.sync 拉取会话列表。"""
    if not cookies_str:
        return []

    data_obj = {'fetchNum': int(fetch_num)}
    data_val = json.dumps(data_obj, separators=(',', ':'), ensure_ascii=False)
    cookies = trans_cookies(cookies_str)
    token = (cookies.get('_m_h5_tk') or '').split('_')[0]
    # 注意：真实毫秒时间戳，不要用 int(time.time())*1000
    t = str(int(time.time() * 1000))
    params = {
        'jsv': '2.7.2',
        'appKey': '34839810',
        't': t,
        'sign': generate_sign(t, token, data_val),
        'v': '3.0',
        'type': 'originaljson',
        'accountSite': 'xianyu',
        'dataType': 'json',
        'timeout': '20000',
        'api': 'mtop.taobao.idlemessage.pc.session.sync',
        'sessionOption': 'AutoLoginOnly',
        'spm_cnt': 'a21ybx.im.0.0',
    }
    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.goofish.com',
        'referer': 'https://www.goofish.com/',
        'user-agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
        ),
        'cookie': cookies_str,
    }

    try:
        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.post(
                'https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.session.sync/3.0/',
                params=params,
                data={'data': data_val},
                headers=headers,
            ) as resp:
                res_json = await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f'拉取会话列表失败: {e}')
        return []

    ret = res_json.get('ret') or []
    if not any('SUCCESS' in str(r) for r in ret):
        logger.warning(f'会话列表 API 失败: {ret}')
        return []

    data = res_json.get('data') or {}
    sessions_raw = data.get('sessions') or []
    result: List[Dict[str, Any]] = []
    for item in sessions_raw:
        if not isinstance(item, dict):
            continue
        parsed = parse_session_item(item)
        # sessionType=1 真人聊天；过滤系统/互动通知
        st = parsed.get('session_type') or 0
        if st and st not in (0, 1):
            continue
        if not parsed.get('chat_id'):
            continue
        result.append(parsed)
    return result
