# -*- coding: utf-8 -*-
"""从闲鱼链接/文本解析商品 ID、卖家 userId。"""

from __future__ import annotations

import json
import re
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse


def _digits(v) -> str:
    s = str(v or '').strip()
    m = re.search(r'(\d{5,})', s)
    return m.group(1) if m else ''


def parse_goofish_ids(raw: str) -> Dict[str, str]:
    """
    解析个人主页 / 商品详情（含超长埋点参数）链接。
    返回 {seller_user_id, item_id, cleaned_url}
    """
    text = unquote(str(raw or '').strip())
    # 去掉首尾引号/空白
    text = text.strip().strip('"').strip("'")
    out = {'seller_user_id': '', 'item_id': '', 'cleaned_url': ''}

    if not text:
        return out

    # 纯数字：优先当 userId（卖家监控场景）
    if re.fullmatch(r'\d{5,}', text):
        out['seller_user_id'] = text
        return out

    # 补全协议方便 urlparse
    url_text = text
    if 'goofish.com' in text or 'xianyu' in text.lower():
        if not re.match(r'^https?://', text, re.I):
            url_text = 'https://' + text.lstrip('/')

    seller = ''
    item_id = ''

    try:
        parsed = urlparse(url_text)
        qs = parse_qs(parsed.query, keep_blank_values=False)

        def qget(*keys):
            for k in keys:
                vals = qs.get(k) or qs.get(k.lower()) or []
                if vals:
                    d = _digits(vals[0])
                    if d:
                        return d
            return ''

        # 个人主页
        seller = qget('userId', 'sellerId', 'seller_id', 'user_id')
        # 商品页核心参数：只取 query 里的 id / itemId（忽略 JSON 埋点里的杂项）
        if 'item' in (parsed.path or '').lower() or 'goofish.com' in (parsed.netloc or ''):
            item_id = qget('id', 'itemId', 'item_id')

        # trackParamsJson / extra 里再兜底 item_id
        if not item_id:
            for key in ('trackParamsJson', 'track_params', 'extra'):
                raw_json = (qs.get(key) or [''])[0]
                if not raw_json:
                    continue
                try:
                    obj = json.loads(raw_json)
                    if isinstance(obj, dict):
                        item_id = _digits(
                            obj.get('item_id') or obj.get('itemId') or obj.get('id') or ''
                        )
                        if item_id:
                            break
                except Exception:
                    m = re.search(r'"item_id"\s*:\s*"?(\d{6,})"?', raw_json)
                    if m:
                        item_id = m.group(1)
                        break
    except Exception:
        pass

    # 正则兜底（兼容非标准粘贴）
    if not seller:
        m = re.search(r'(?:userId|sellerId|seller_id|user_id)=(\d{5,})', text, re.I)
        if m:
            seller = m.group(1)
    if not item_id:
        # 优先 item?id= / /item/123
        m = re.search(r'(?:/item(?:\?|/)|item\?|[?&])id=(\d{6,})', text, re.I)
        if m:
            item_id = m.group(1)
        if not item_id:
            m = re.search(r'"item_id"\s*:\s*"?(\d{6,})"?', text)
            if m:
                item_id = m.group(1)

    # 注意：不要用宽泛的 uid= ，避免误伤埋点参数

    out['seller_user_id'] = seller
    out['item_id'] = item_id
    if item_id:
        out['cleaned_url'] = f'https://www.goofish.com/item?id={item_id}'
    elif seller:
        out['cleaned_url'] = f'https://www.goofish.com/personal?userId={seller}'
    return out


def extract_seller_from_item_detail(detail: dict, item_id: str = '') -> Tuple[str, Optional[dict]]:
    """从 mtop.taobao.idle.pc.detail 等返回里抠卖家 ID + 商品摘要。"""
    if not isinstance(detail, dict):
        return '', None

    data = detail.get('data') if isinstance(detail.get('data'), dict) else detail
    if not isinstance(data, dict):
        data = {}

    seller_uid = ''
    seller_obj = None
    for path in (
        ('sellerDO',),
        ('seller',),
        ('sellerInfo',),
        ('itemDO', 'seller'),
        ('item', 'seller'),
        ('module', 'seller'),
        ('module', 'sellerInfo'),
        ('data', 'sellerDO'),
    ):
        cur = data
        ok = True
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                ok = False
                break
            cur = cur[k]
        if ok and isinstance(cur, dict):
            seller_uid = str(
                cur.get('userId')
                or cur.get('sellerId')
                or cur.get('uid')
                or cur.get('peerUserId')
                or ''
            )
            # 避免把商品 id 误当成卖家
            if seller_uid and seller_uid != str(item_id or ''):
                seller_obj = cur
                break
            seller_uid = ''

    if not seller_uid:
        blob = json.dumps(detail, ensure_ascii=False)
        # 常见字段名
        for pat in (
            r'"sellerId"\s*:\s*"?(\d{5,})"?',
            r'"userId"\s*:\s*"?(\d{5,})"?',
            r'"peerUserId"\s*:\s*"?(\d{5,})"?',
            r'"sellerUserId"\s*:\s*"?(\d{5,})"?',
        ):
            for m in re.finditer(pat, blob):
                cand = m.group(1)
                if cand and cand != str(item_id or ''):
                    seller_uid = cand
                    break
            if seller_uid:
                break

    snap = None
    if seller_uid:
        item_do = data.get('itemDO') if isinstance(data.get('itemDO'), dict) else {}
        title = str(
            item_do.get('title')
            or data.get('title')
            or (data.get('item') or {}).get('title')
            or ''
        )
        price = str(
            item_do.get('soldPrice')
            or item_do.get('price')
            or data.get('price')
            or ''
        )
        nick = ''
        if isinstance(seller_obj, dict):
            nick = str(
                seller_obj.get('nick')
                or seller_obj.get('userName')
                or seller_obj.get('displayName')
                or seller_obj.get('userNick')
                or ''
            )
        snap = {
            'item_id': str(item_id or ''),
            'title': title,
            'price': price,
            'seller_nick': nick,
        }
    return seller_uid, snap
