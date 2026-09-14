"""闲鱼卖家订单列表同步：优先 mtop sold.list，失败则 Playwright 拦截。"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

import aiohttp
from loguru import logger

from utils.xianyu_utils import generate_sign, trans_cookies

SOLD_APIS = [
    ('mtop.idle.web.trade.sold.list', '1.0'),
    ('mtop.taobao.idle.trade.sold.list', '1.0'),
    ('mtop.idle.web.trade.order.sold.list', '1.0'),
    ('mtop.idle.trade.order.list', '1.0'),
    ('mtop.taobao.idle.trade.order.list', '1.0'),
    ('mtop.idle.web.trade.order.list', '1.0'),
    # 部分端可能与 bought 同结构但 role=seller
    ('mtop.idle.web.trade.bought.list', '1.0'),
]

# 额外尝试的 data 形态（不同端字段不一致）
DATA_VARIANTS = [
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status},
    lambda page, status: {'pageNum': int(page), 'pageSize': 20, 'orderStatus': status},
    lambda page, status: {'pageNumber': int(page), 'rowsPerPage': 20, 'orderStatus': status, 'role': 'seller'},
    lambda page, status: {'pageNumber': int(page), 'tabCode': status or 'ALL', 'role': 'seller'},
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status, 'sellerId': ''},
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status, 'role': 'seller'},
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status, 'type': 'sold'},
]

STATUS_MAP = {
    'ALL': None,
    'NOT_PAY': 'processing',
    'NOT_SHIP': 'pending_ship',
    'SHIPPED': 'shipped',
    'NOT_RATE': 'completed',
    'REFUND': 'refunding',
    'trade_success': 'completed',
    'TRADE_SUCCESS': 'completed',
    'refund_success': 'cancelled',
    'CLOSED': 'cancelled',
    'CANCELLED': 'cancelled',
    'PAID': 'pending_ship',
    'WAIT_SELLER_SEND_GOODS': 'pending_ship',
    'WAIT_BUYER_PAY': 'processing',
    'WAIT_BUYER_CONFIRM_GOODS': 'shipped',
    'TRADE_CLOSED': 'cancelled',
    'TRADE_FINISHED': 'completed',
    'seller_send_goods': 'shipped',
    'buyer_confirm_goods': 'completed',
}

_DISCOVERED_API_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
    'discovered_sold_api.json',
)


def _load_discovered_apis() -> List[Tuple[str, str]]:
    try:
        if not os.path.isfile(_DISCOVERED_API_PATH):
            return []
        with open(_DISCOVERED_API_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        out = []
        for it in raw if isinstance(raw, list) else [raw]:
            if isinstance(it, dict) and it.get('api'):
                out.append((str(it['api']), str(it.get('version') or '1.0')))
            elif isinstance(it, (list, tuple)) and len(it) >= 1:
                out.append((str(it[0]), str(it[1] if len(it) > 1 else '1.0')))
        return out
    except Exception:
        return []


def remember_sold_api(api: str, version: str = '1.0'):
    """Playwright / 命中后缓存真实 API，下次优先尝试。"""
    if not api or 'bought.list' in api:
        # bought.list 是买家侧，不作为 sold 首选缓存
        if 'sold' not in api and 'seller' not in api:
            return
    try:
        os.makedirs(os.path.dirname(_DISCOVERED_API_PATH), exist_ok=True)
        existing = _load_discovered_apis()
        pair = (api, version or '1.0')
        if pair in existing:
            existing = [pair] + [x for x in existing if x != pair]
        else:
            existing = [pair] + existing
        payload = [{'api': a, 'version': v} for a, v in existing[:8]]
        with open(_DISCOVERED_API_PATH, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f'已缓存卖家订单 API: {api}/{version}')
    except Exception as e:
        logger.debug(f'缓存 sold API 失败: {e}')


def get_sold_api_candidates() -> List[Tuple[str, str]]:
    discovered = _load_discovered_apis()
    seen = set()
    out: List[Tuple[str, str]] = []
    for item in discovered + list(SOLD_APIS):
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _map_status(raw: Any) -> str:
    if raw is None:
        return 'unknown'
    s = str(raw).strip()
    if s in STATUS_MAP and STATUS_MAP[s]:
        return STATUS_MAP[s]
    low = s.lower()
    for k, v in STATUS_MAP.items():
        if v and k.lower() == low:
            return v
    if '发货' in s and '待' in s:
        return 'pending_ship'
    if '收货' in s or '运输' in s or '配送' in s:
        return 'shipped'
    if '成功' in s or '完成' in s or '评价' in s:
        return 'completed'
    if '退' in s:
        return 'refunding'
    if '关闭' in s or '取消' in s:
        return 'cancelled'
    if '付款' in s or '支付' in s:
        return 'processing'
    return 'unknown'


def _pick(d: Any, *path: str, default: Any = '') -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def parse_sold_order_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """兼容 bought/sold 列表卡片结构。"""
    if not isinstance(item, dict):
        return None

    common = item.get('commonData') or item.get('common') or {}
    content = _pick(item, 'content', 'data', default={}) or {}
    head = _pick(item, 'head', 'data', default={}) or {}
    detail = content.get('detailInfo') or content.get('itemInfo') or {}
    price_info = content.get('priceInfo') or {}
    user_info = head.get('userInfo') or {}

    order_id = str(
        common.get('orderId')
        or common.get('bizOrderId')
        or item.get('orderId')
        or item.get('bizOrderId')
        or item.get('id')
        or ''
    )
    if not order_id or not re.match(r'^\d{6,}$', order_id):
        # 宽松：只要有 orderId 字段都收下
        if not order_id:
            return None

    item_id = str(
        common.get('itemId')
        or detail.get('itemId')
        or detail.get('auctionId')
        or item.get('itemId')
        or ''
    )
    buyer_id = str(
        common.get('peerUserId')
        or common.get('buyerId')
        or user_info.get('userId')
        or item.get('buyerId')
        or ''
    )
    amount = (
        price_info.get('price')
        or price_info.get('soldPrice')
        or detail.get('price')
        or item.get('amount')
        or ''
    )
    qty = price_info.get('buyAmount') or item.get('quantity') or 1
    raw_status = (
        common.get('tradeStatusEnum')
        or common.get('orderStatus')
        or head.get('statusViewMsg')
        or item.get('status')
    )
    title = detail.get('auctionTitle') or detail.get('title') or item.get('title') or ''
    pic = detail.get('auctionPic') or detail.get('picUrl') or detail.get('mainPic') or ''

    return {
        'order_id': order_id,
        'item_id': item_id,
        'buyer_id': buyer_id,
        'buyer_nick': user_info.get('userNick') or user_info.get('nick') or '',
        'buyer_avatar': user_info.get('userIcon') or user_info.get('avatar') or '',
        'amount': str(amount) if amount is not None else '',
        'quantity': qty,
        'status': _map_status(raw_status),
        'raw_status': str(raw_status or ''),
        'item_title': title,
        'item_pic': pic,
        'created_at': head.get('createTime') or common.get('createTime') or '',
    }


def _walk_collect_orders(node: Any, out: List[Dict[str, Any]], depth: int = 0):
    """递归从任意 JSON 结构里抠订单卡片。"""
    if depth > 8 or node is None:
        return
    if isinstance(node, dict):
        if any(k in node for k in ('orderId', 'bizOrderId', 'commonData')):
            parsed = parse_sold_order_item(node)
            if parsed:
                out.append(parsed)
        for v in node.values():
            _walk_collect_orders(v, out, depth + 1)
    elif isinstance(node, list):
        for it in node:
            _walk_collect_orders(it, out, depth + 1)


def extract_orders_from_mtop_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = payload.get('data') if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    items = data.get('items') or data.get('list') or data.get('orders') or []
    if not items and isinstance(data.get('cardList'), list):
        items = data.get('cardList')
    rows = []
    for it in items or []:
        if isinstance(it, dict) and 'cardData' in it:
            it = it.get('cardData') or it
        parsed = parse_sold_order_item(it if isinstance(it, dict) else {})
        if parsed:
            rows.append(parsed)
    if not rows:
        # 兜底递归扫描
        found: List[Dict[str, Any]] = []
        _walk_collect_orders(payload, found)
        rows = found
    # 去重
    seen = set()
    uniq = []
    for r in rows:
        oid = r.get('order_id')
        if oid and oid not in seen:
            seen.add(oid)
            uniq.append(r)
    return uniq


async def _call_sold_api(
    cookies_str: str,
    api: str,
    version: str,
    data_obj: Dict[str, Any],
    timeout: float = 20.0,
) -> Dict[str, Any]:
    cookies = trans_cookies(cookies_str)
    token = (cookies.get('_m_h5_tk') or '').split('_')[0]
    t = str(int(time.time() * 1000))
    data_val = json.dumps(data_obj, separators=(',', ':'), ensure_ascii=False)
    params = {
        'jsv': '2.7.2',
        'appKey': '34839810',
        't': t,
        'sign': generate_sign(t, token, data_val),
        'v': version,
        'type': 'originaljson',
        'accountSite': 'xianyu',
        'dataType': 'json',
        'timeout': '20000',
        'api': api,
        'sessionOption': 'AutoLoginOnly',
        'spm_cnt': 'a21ybx.order.0.0',
    }
    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.goofish.com',
        'referer': 'https://www.goofish.com/',
        'user-agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
    }
    url = f'https://h5api.m.goofish.com/h5/{api}/{version}/'
    cookie_header = '; '.join(f'{k}={unquote(v) if k == "tracknick" else v}' for k, v in cookies.items())
    headers['cookie'] = cookie_header

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, data={'data': data_val}, headers=headers, timeout=timeout) as resp:
            return await resp.json(content_type=None)


async def fetch_sold_orders_via_mtop(
    cookies_str: str,
    order_status: str = 'ALL',
    max_pages: int = 3,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """尝试卖家订单 mtop 接口分页拉取。返回 (rows, diagnostics)。"""
    all_rows: List[Dict[str, Any]] = []
    working: Optional[Tuple[str, str, Dict[str, Any]]] = None
    diags: List[str] = []

    for api, ver in get_sold_api_candidates():
        for maker in DATA_VARIANTS:
            data_obj = maker(1, order_status)
            try:
                res = await _call_sold_api(cookies_str, api, ver, data_obj)
                ret = (res.get('ret') or [''])[0]
                diags.append(f'{api}:{ret}')
                if 'SUCCESS' not in str(ret):
                    continue
                rows = extract_orders_from_mtop_payload(res)
                if rows:
                    working = (api, ver, data_obj)
                    all_rows.extend(rows)
                    remember_sold_api(api, ver)
                    logger.info(f'卖家订单 mtop 命中: {api} data={list(data_obj.keys())} 第1页 {len(rows)} 条')
                    break
                diags.append(f'{api}:SUCCESS_EMPTY')
            except Exception as e:
                diags.append(f'{api}:EX:{e}')
                logger.debug(f'卖家订单 API 异常 {api}: {e}')
        if working:
            break

    if not working:
        return [], diags[-12:]

    api, ver, base_data = working
    for page in range(2, max_pages + 1):
        try:
            data_obj = dict(base_data)
            if 'pageNumber' in data_obj:
                data_obj['pageNumber'] = page
            if 'pageNum' in data_obj:
                data_obj['pageNum'] = page
            res = await _call_sold_api(cookies_str, api, ver, data_obj)
            if 'SUCCESS' not in str((res.get('ret') or [''])[0]):
                break
            rows = extract_orders_from_mtop_payload(res)
            if not rows:
                break
            all_rows.extend(rows)
            data = res.get('data') or {}
            if str(data.get('nextPage') or '').lower() not in ('true', '1'):
                break
        except Exception:
            break
    return all_rows, diags[-12:]


def _parse_api_from_url(url: str) -> Tuple[str, str]:
    m = re.search(r'/h5/([^/]+)/([\d.]+)/', url or '')
    if m:
        return m.group(1), m.group(2)
    return '', '1.0'


async def fetch_sold_orders_via_playwright(
    cookies_str: str,
    headless: bool = True,
    timeout_ms: int = 60000,
) -> List[Dict[str, Any]]:
    """打开卖出页，拦截任意带 orderId 的 mtop 响应，并缓存命中的 API。"""
    from playwright.async_api import async_playwright

    cookies = trans_cookies(cookies_str)
    pw_cookies = []
    for k, v in cookies.items():
        for domain in ('.goofish.com', '.taobao.com', '.alibaba.com', 'www.goofish.com'):
            pw_cookies.append({'name': k, 'value': v, 'domain': domain, 'path': '/'})

    captured: List[Dict[str, Any]] = []
    urls = [
        'https://www.goofish.com/order-list?role=seller',
        'https://www.goofish.com/order-list?type=sell',
        'https://www.goofish.com/order-list',
        'https://www.goofish.com/im',
        'https://www.goofish.com/personal',
        'https://seller.goofish.com/',
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ],
        )
        context = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            ),
            viewport={'width': 1440, 'height': 900},
            locale='zh-CN',
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await context.add_cookies(pw_cookies)
        page = await context.new_page()

        async def on_response(response):
            try:
                url = response.url or ''
                if 'h5api.m.goofish.com' not in url and 'h5api.m.taobao.com' not in url:
                    return
                body = await response.body()
                text = body.decode('utf-8', errors='ignore')
                if 'orderId' not in text and 'bizOrderId' not in text:
                    return
                data = json.loads(text)
                rows = extract_orders_from_mtop_payload(data)
                if rows:
                    captured.extend(rows)
                    api, ver = _parse_api_from_url(url)
                    if api:
                        remember_sold_api(api, ver)
                    logger.info(f'Playwright 拦截订单 {len(rows)} 条 from {url[:120]}')
            except Exception:
                return

        page.on('response', on_response)
        try:
            try:
                await page.goto('https://www.goofish.com/', wait_until='domcontentloaded', timeout=timeout_ms)
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            for u in urls:
                try:
                    await page.goto(u, wait_until='domcontentloaded', timeout=timeout_ms)
                    await page.wait_for_timeout(3500)
                    for label in ('我卖出的', '卖出', '已卖出', '待发货', '全部', '订单', '出售'):
                        try:
                            loc = page.get_by_text(label, exact=False).first
                            if await loc.count() > 0:
                                await loc.click(timeout=2000)
                                await page.wait_for_timeout(3500)
                        except Exception:
                            pass
                    try:
                        for _ in range(3):
                            await page.mouse.wheel(0, 1800)
                            await page.wait_for_timeout(1200)
                    except Exception:
                        pass
                    if captured:
                        break
                except Exception as e:
                    logger.debug(f'打开卖出页失败 {u}: {e}')
        finally:
            await browser.close()

    seen = set()
    uniq = []
    for r in captured:
        oid = r.get('order_id')
        if oid and oid not in seen:
            seen.add(oid)
            uniq.append(r)
    return uniq


async def sync_sold_orders_to_db(
    cookie_id: str,
    cookies_str: str,
    order_status: str = 'ALL',
    use_playwright_fallback: bool = True,
) -> Dict[str, Any]:
    """拉取卖家订单并写入本地 DB。优先在线实例，其次 mtop，再次 Playwright。"""
    from db_manager import db_manager

    rows: List[Dict[str, Any]] = []
    via = 'none'
    diagnostics: List[str] = []

    # 1) 在线实例（签名/Cookie 最新）
    try:
        from XianyuAutoAsync import XianyuLive
        live = XianyuLive.get_instance(cookie_id)
        if live:
            rows = await live.fetch_sold_order_list(order_status=order_status)
            diagnostics = list(getattr(live, '_last_sold_fetch_diag', []) or [])
            if rows:
                via = 'live'
                cookies_str = live.cookies_str or cookies_str
    except Exception as e:
        diagnostics.append(f'live:EX:{e}')
        logger.debug(f'【{cookie_id}】在线实例拉订单失败: {e}')

    # 2) 独立 mtop
    if not rows:
        rows, mtop_diag = await fetch_sold_orders_via_mtop(cookies_str, order_status=order_status)
        diagnostics.extend(mtop_diag)
        via = 'mtop' if rows else via

    # 3) Playwright 拦截
    if not rows and use_playwright_fallback:
        logger.info(f'【{cookie_id}】mtop/live 未拿到卖家订单，尝试 Playwright 拦截')
        rows = await fetch_sold_orders_via_playwright(cookies_str)
        via = 'playwright' if rows else via
        if not rows:
            diagnostics.append('playwright:EMPTY')

    saved = 0
    save_errors: List[str] = []
    for r in rows:
        try:
            oid = str(r.get('order_id') or '').strip()
            if not oid:
                save_errors.append('empty_order_id')
                continue
            created_at = r.get('created_at') or None
            if created_at == '':
                created_at = None
            ok = db_manager.insert_or_update_order(
                order_id=oid,
                item_id=r.get('item_id') or None,
                buyer_id=r.get('buyer_id') or None,
                quantity=str(r.get('quantity') or 1),
                amount=str(r.get('amount') or '') or None,
                order_status=r.get('status') or 'unknown',
                cookie_id=cookie_id,
                created_at=created_at,
                item_title=r.get('item_title') or None,
                item_pic=r.get('item_pic') or None,
                buyer_nick=r.get('buyer_nick') or None,
                raw_status=r.get('raw_status') or None,
                order_role='sold',
            )
            if ok:
                saved += 1
                title = r.get('item_title') or ''
                item_id = r.get('item_id') or ''
                if item_id and title:
                    try:
                        db_manager.save_item_basic_info(
                            cookie_id=cookie_id,
                            item_id=item_id,
                            item_title=title,
                            item_price=str(r.get('amount') or ''),
                        )
                    except Exception:
                        pass
            else:
                save_errors.append(f'{oid}:insert_returned_false')
        except Exception as e:
            save_errors.append(f'{r.get("order_id")}:{e}')
            logger.error(f'【{cookie_id}】订单入库异常: {e}')

    soft_ok = len(rows) > 0
    return {
        'success': soft_ok,
        'via': via,
        'fetched': len(rows),
        'saved': saved,
        'orders': rows,
        'diagnostics': (diagnostics + save_errors)[-20:],
        'message': (
            None
            if soft_ok
            else '未能拉取到卖出订单（接口受限或 Cookie 失效）。详见 diagnostics。'
        ),
    }


BOUGHT_APIS = [
    ('mtop.idle.web.trade.bought.list', '1.0'),
    ('mtop.taobao.idle.trade.bought.list', '1.0'),
    ('mtop.idle.web.trade.order.bought.list', '1.0'),
    ('mtop.idle.trade.bought.list', '1.0'),
]

BOUGHT_DATA_VARIANTS = [
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status},
    lambda page, status: {'pageNum': int(page), 'pageSize': 20, 'orderStatus': status},
    lambda page, status: {'pageNumber': int(page), 'rowsPerPage': 20, 'orderStatus': status, 'role': 'buyer'},
    lambda page, status: {'pageNumber': int(page), 'tabCode': status or 'ALL', 'role': 'buyer'},
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status, 'role': 'buyer'},
    lambda page, status: {'pageNumber': int(page), 'orderStatus': status, 'type': 'bought'},
]


async def fetch_bought_orders_via_mtop(
    cookies_str: str,
    order_status: str = 'ALL',
    max_pages: int = 3,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """尝试买家订单 mtop 接口分页拉取。返回 (rows, diagnostics)。"""
    all_rows: List[Dict[str, Any]] = []
    working: Optional[Tuple[str, str, Dict[str, Any]]] = None
    diags: List[str] = []

    for api, ver in BOUGHT_APIS:
        for maker in BOUGHT_DATA_VARIANTS:
            data_obj = maker(1, order_status)
            try:
                res = await _call_sold_api(cookies_str, api, ver, data_obj)
                ret = (res.get('ret') or [''])[0]
                diags.append(f'{api}:{ret}')
                if 'SUCCESS' not in str(ret):
                    continue
                rows = extract_orders_from_mtop_payload(res)
                if rows:
                    working = (api, ver, data_obj)
                    all_rows.extend(rows)
                    logger.info(f'买家订单 mtop 命中: {api} 第1页 {len(rows)} 条')
                    break
                diags.append(f'{api}:SUCCESS_EMPTY')
            except Exception as e:
                diags.append(f'{api}:EX:{e}')
                logger.debug(f'买家订单 API 异常 {api}: {e}')
        if working:
            break

    if not working:
        return [], diags[-12:]

    api, ver, base_data = working
    for page in range(2, max_pages + 1):
        try:
            data_obj = dict(base_data)
            if 'pageNumber' in data_obj:
                data_obj['pageNumber'] = page
            if 'pageNum' in data_obj:
                data_obj['pageNum'] = page
            res = await _call_sold_api(cookies_str, api, ver, data_obj)
            if 'SUCCESS' not in str((res.get('ret') or [''])[0]):
                break
            rows = extract_orders_from_mtop_payload(res)
            if not rows:
                break
            all_rows.extend(rows)
            data = res.get('data') or {}
            if str(data.get('nextPage') or '').lower() not in ('true', '1'):
                break
        except Exception:
            break
    return all_rows, diags[-12:]


async def sync_bought_orders_to_db(
    cookie_id: str,
    cookies_str: str,
    order_status: str = 'ALL',
) -> Dict[str, Any]:
    """拉取买家订单并写入本地 DB（order_role=bought）。"""
    from db_manager import db_manager

    rows, diagnostics = await fetch_bought_orders_via_mtop(cookies_str, order_status=order_status)
    via = 'mtop' if rows else 'none'
    saved = 0
    save_errors: List[str] = []
    for r in rows:
        try:
            oid = str(r.get('order_id') or '').strip()
            if not oid:
                save_errors.append('empty_order_id')
                continue
            created_at = r.get('created_at') or None
            if created_at == '':
                created_at = None
            ok = db_manager.insert_or_update_order(
                order_id=oid,
                item_id=r.get('item_id') or None,
                buyer_id=r.get('buyer_id') or None,
                quantity=str(r.get('quantity') or 1),
                amount=str(r.get('amount') or '') or None,
                order_status=r.get('status') or 'unknown',
                cookie_id=cookie_id,
                created_at=created_at,
                item_title=r.get('item_title') or None,
                item_pic=r.get('item_pic') or None,
                buyer_nick=r.get('buyer_nick') or None,
                raw_status=r.get('raw_status') or None,
                order_role='bought',
            )
            if ok:
                saved += 1
            else:
                save_errors.append(f'{oid}:insert_returned_false')
        except Exception as e:
            save_errors.append(f'{r.get("order_id")}:{e}')
            logger.error(f'【{cookie_id}】买入订单入库异常: {e}')

    soft_ok = len(rows) > 0
    return {
        'success': soft_ok,
        'via': via,
        'fetched': len(rows),
        'saved': saved,
        'orders': rows,
        'diagnostics': (diagnostics + save_errors)[-20:],
        'message': (
            None
            if soft_ok
            else '未能拉取到买入订单（接口受限或 Cookie 失效）。详见 diagnostics。'
        ),
    }
