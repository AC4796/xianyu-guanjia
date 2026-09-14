# -*- coding: utf-8 -*-
"""代采代发：买家付款后向上家快捷购买，上家发货/卡密后转发给买家。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


SHIP_TRIGGER_TEXTS = {
    '[我已发货，请查看发货凭证]',
    '[你已发货]',
    '已发货',
    '我已发货',
}

STATUS_LABELS = {
    'pending_buy': '待采购',
    'buying': '采购中',
    'waiting_ship': '等上家发货',
    'need_manual_pay': '需手动支付上家',
    'buy_failed': '采购失败',
    'forwarded': '已转发买家',
    'done': '已完成',
}


def is_ship_notice(text: str) -> bool:
    t = str(text or '').strip()
    if not t:
        return False
    if t in SHIP_TRIGGER_TEXTS:
        return True
    return ('发货' in t and '凭证' in t) or t.startswith('[我已发货')


def extract_forwardable_text(send_message: str, raw_message: Any = None) -> str:
    """尽量从系统文案 / 卡片 JSON 里抠出可转发给买家的内容。"""
    texts = []
    base = str(send_message or '').strip()
    if base and base not in ('[卡片消息]', '[图片]'):
        texts.append(base)

    if isinstance(raw_message, dict):
        try:
            # 常见卡片路径
            node = raw_message
            for k in ('1', '6', '3'):
                if isinstance(node, dict) and k in node:
                    node = node[k]
            payload = None
            if isinstance(node, dict) and '5' in node:
                payload = node.get('5')
            if isinstance(payload, str) and payload.strip().startswith('{'):
                card = json.loads(payload)
                dx = ((card.get('dxCard') or {}).get('item') or {}).get('main') or {}
                ex = dx.get('exContent') or {}
                for key in ('title', 'content', 'subTitle', 'desc', 'text'):
                    v = ex.get(key)
                    if isinstance(v, str) and v.strip():
                        texts.append(v.strip())
                # 递归找像卡密的长串
                blob = json.dumps(card, ensure_ascii=False)
                for m in re.findall(r'[A-Za-z0-9_\-]{8,}', blob):
                    if m.lower() in ('excontent', 'dxcard', 'goofish'):
                        continue
                    if len(m) >= 10:
                        texts.append(m)
        except Exception:
            pass

    # 去重保序
    seen = set()
    out = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return '\n'.join(out) if out else base


def _format_address(order: Optional[dict]) -> str:
    if not order:
        return ''
    name = str(order.get('receiver_name') or '').strip()
    phone = str(order.get('receiver_phone') or '').strip()
    addr = str(order.get('receiver_address') or '').strip()
    city = str(order.get('receiver_city') or '').strip()
    parts = [p for p in (name, phone, city, addr) if p]
    return ' '.join(parts)


async def _load_order_address(live, order_id: str, item_id: str, buyer_id: str) -> str:
    from db_manager import db_manager

    order = None
    try:
        # 尽量带收货字段
        rows = db_manager.get_orders_by_cookie(live.cookie_id, limit=200) or []
        order = next((o for o in rows if str(o.get('order_id')) == str(order_id)), None)
    except Exception:
        order = None
    addr = _format_address(order)
    if addr:
        return addr
    # 再拉一次订单详情
    try:
        if hasattr(live, 'fetch_order_detail_info'):
            detail = await live.fetch_order_detail_info(order_id, item_id, buyer_id)
            if isinstance(detail, dict):
                addr = _format_address({
                    'receiver_name': detail.get('receiver_name') or detail.get('name'),
                    'receiver_phone': detail.get('receiver_phone') or detail.get('phone'),
                    'receiver_address': detail.get('receiver_address') or detail.get('address'),
                    'receiver_city': detail.get('receiver_city') or detail.get('city'),
                })
    except Exception:
        pass
    return addr


async def _notify_upstream_seller(
    live,
    *,
    source_seller_id: str,
    source_item_id: str,
    address: str,
    buyer_order_id: str,
    websocket=None,
) -> Optional[str]:
    """把收货信息发给上家，返回 source_chat_id（若有）。"""
    if not source_seller_id:
        return None
    text = (
        f'【代发采购】请按以下信息发货/发卡密：\n'
        f'买家订单：{buyer_order_id}\n'
        f'货源商品：{source_item_id}\n'
    )
    if address:
        text += f'收货信息：{address}\n'
    else:
        text += '收货信息暂缺，若为虚拟卡密请直接发卡密到本会话。\n'
    text += '发货或发卡密后我会自动转发给我的买家，谢谢。'

    chat_id = ''
    try:
        if hasattr(live, 'ensure_chat_conversation'):
            ens = await live.ensure_chat_conversation(
                to_user_id=str(source_seller_id),
                item_id=str(source_item_id or ''),
                item_title='代发采购',
            )
            chat_id = str((ens or {}).get('chat_id') or '')
    except Exception:
        chat_id = ''

    try:
        if websocket and chat_id:
            await live.send_msg(websocket, chat_id, str(source_seller_id), text)
        elif hasattr(live, 'send_msg_once'):
            await live.send_msg_once(str(source_seller_id), str(source_item_id or ''), text)
    except Exception:
        pass
    return chat_id or None


async def try_start_dropship_on_payment(
    live,
    *,
    order_id: str,
    local_item_id: str,
    buyer_id: str,
    buyer_chat_id: str,
    websocket=None,
) -> Dict[str, Any]:
    """
    若本地商品绑定了代发，则创建任务并尝试快捷购买上家商品。
    返回 {handled: bool, ...}；handled=True 表示应跳过普通卡密发货。
    """
    from db_manager import db_manager
    from utils.xy_quick_buy import quick_buy_item

    binding = db_manager.find_dropship_binding(live.cookie_id, local_item_id)
    if not binding:
        return {'handled': False}

    source_item_id = str(binding.get('source_item_id') or '')
    source_seller_id = str(binding.get('seller_user_id') or '')
    if not source_item_id:
        return {'handled': False}

    job = db_manager.create_dropship_job({
        'cookie_id': live.cookie_id,
        'watch_id': int(binding.get('watch_id') or 0),
        'buyer_order_id': order_id,
        'local_item_id': local_item_id,
        'source_item_id': source_item_id,
        'source_seller_id': source_seller_id,
        'buyer_id': buyer_id,
        'buyer_chat_id': buyer_chat_id,
        'status': 'pending_buy',
    })
    if not job:
        return {'handled': True, 'success': False, 'message': '创建代发任务失败'}

    tip = (
        '已收到付款，正在向上家采购，请稍候；'
        '上家发货/发卡密后会自动转发给您。'
    )
    try:
        if websocket and buyer_chat_id and buyer_id:
            await live.send_msg(websocket, buyer_chat_id, buyer_id, tip)
    except Exception:
        pass

    # 先把地址发给上家（即使购买需人工，也能先沟通）
    address = await _load_order_address(live, order_id, local_item_id, buyer_id)
    source_chat = await _notify_upstream_seller(
        live,
        source_seller_id=source_seller_id,
        source_item_id=source_item_id,
        address=address,
        buyer_order_id=order_id,
        websocket=websocket,
    )
    if source_chat:
        db_manager.update_dropship_job(int(job['id']), source_chat_id=source_chat)

    pay_pwd = ''
    try:
        cfg = live._get_automation_cfg() if hasattr(live, '_get_automation_cfg') else {}
        pay_pwd = str(cfg.get('dropship_pay_password') or '')
    except Exception:
        pay_pwd = ''
    if not pay_pwd:
        try:
            pay_pwd = db_manager.get_system_setting(f'dropship_pay_password:{live.cookie_id}') or ''
        except Exception:
            pay_pwd = ''

    db_manager.update_dropship_job(int(job['id']), status='buying')
    buy_res = await quick_buy_item(live.cookies_str, source_item_id, pay_password=pay_pwd or None)
    if buy_res.get('need_manual'):
        status = 'need_manual_pay'
    elif buy_res.get('success'):
        status = 'waiting_ship'
    else:
        status = 'buy_failed'
    db_manager.update_dropship_job(
        int(job['id']),
        buy_result=json.dumps(buy_res, ensure_ascii=False)[:2000],
        status=status,
        last_error='' if status != 'buy_failed' else str(buy_res.get('message') or '购买失败'),
    )

    if status == 'waiting_ship':
        follow = '已向上家提交购买，等待上家发货/发卡密后自动转发给您。'
    elif status == 'need_manual_pay':
        url = buy_res.get('url') or ''
        follow = f'已打开上家购买页，需您手动完成支付确认。{("链接：" + url) if url else ""}'
    else:
        follow = f'向上家自动购买未成功：{buy_res.get("message") or "未知错误"}。请人工处理该订单。'

    try:
        if websocket and buyer_chat_id and buyer_id and follow:
            await live.send_msg(websocket, buyer_chat_id, buyer_id, follow)
    except Exception:
        pass

    return {
        'handled': True,
        'success': status in ('waiting_ship', 'need_manual_pay'),
        'job_id': job.get('id'),
        'buy': buy_res,
        'message': follow,
    }


def _find_open_job(cookie_id: str, send_user_id: str, item_id: str = '') -> Optional[dict]:
    from db_manager import db_manager

    job = None
    if item_id and item_id not in ('', '未知商品'):
        job = db_manager.find_open_dropship_by_source_item(cookie_id, str(item_id))
    if not job and send_user_id:
        job = db_manager.find_open_dropship_by_source_seller(cookie_id, str(send_user_id))
    return job


async def try_forward_source_inbound(
    live,
    *,
    send_user_id: str,
    chat_id: str,
    send_message: str,
    item_id: str = '',
    raw_message: Any = None,
    websocket=None,
    force_ship: bool = False,
) -> Dict[str, Any]:
    """
    上家会话入站消息转发：
    - 发货系统通知：转发并尽量确认本侧发货
    - 普通文本/卡片（卡密等）：在 waiting_ship / need_manual_pay 期间也转发
    """
    from db_manager import db_manager

    job = _find_open_job(live.cookie_id, send_user_id, item_id)
    if not job:
        return {'handled': False}

    status = str(job.get('status') or '')
    ship = force_ship or is_ship_notice(send_message)
    # 仅在采购相关状态下转发上家内容，避免误转发闲聊
    if not ship and status not in ('waiting_ship', 'need_manual_pay', 'bought', 'buying'):
        return {'handled': False}

    body = extract_forwardable_text(send_message, raw_message)
    if not body:
        return {'handled': False}

    buyer_chat = str(job.get('buyer_chat_id') or '')
    buyer_id = str(job.get('buyer_id') or '')
    prefix = '【代发自动转发·上家发货】' if ship else '【代发自动转发·上家消息】'
    content = f'{prefix}\n{body}'

    forwarded = False
    try:
        if websocket and buyer_chat and buyer_id:
            await live.send_msg(websocket, buyer_chat, buyer_id, content)
            forwarded = True
    except Exception as e:
        db_manager.update_dropship_job(int(job['id']), last_error=f'转发失败: {e}')
        return {'handled': True, 'success': False, 'message': str(e)}

    new_status = 'forwarded' if ship else status
    db_manager.update_dropship_job(
        int(job['id']),
        status=new_status,
        forwarded_content=content[:2000],
        source_chat_id=str(chat_id or job.get('source_chat_id') or ''),
    )

    if ship:
        try:
            if hasattr(live, 'auto_confirm') and job.get('buyer_order_id'):
                await live.auto_confirm(str(job['buyer_order_id']), job.get('local_item_id'))
                db_manager.update_dropship_job(int(job['id']), status='done')
        except Exception:
            pass

    return {'handled': True, 'success': forwarded, 'job_id': job.get('id'), 'ship': ship}


async def try_forward_source_ship(
    live,
    *,
    send_user_id: str,
    chat_id: str,
    send_message: str,
    item_id: str = '',
    websocket=None,
    raw_message: Any = None,
) -> Dict[str, Any]:
    if not is_ship_notice(send_message):
        return {'handled': False}
    return await try_forward_source_inbound(
        live,
        send_user_id=send_user_id,
        chat_id=chat_id,
        send_message=send_message,
        item_id=item_id,
        raw_message=raw_message,
        websocket=websocket,
        force_ship=True,
    )
