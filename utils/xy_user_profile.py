"""闲鱼用户资料：真实昵称 / 头像（mtop.idle.web.user.page.head）"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional
from urllib.parse import unquote

import aiohttp
from loguru import logger

from utils.xianyu_utils import generate_sign, trans_cookies


def parse_cookie_field(cookie_value: str, key: str) -> str:
    if not cookie_value:
        return ''
    for part in cookie_value.split(';'):
        part = part.strip()
        if part.startswith(key + '='):
            try:
                return unquote(part.split('=', 1)[1])
            except Exception:
                return part.split('=', 1)[1]
    return ''


async def fetch_user_head(
    cookies_str: str,
    *,
    self_profile: bool = True,
    user_id: Optional[str] = None,
    timeout: float = 12.0,
) -> Dict[str, Any]:
    """调用 mtop.idle.web.user.page.head 获取昵称与头像。

    Returns:
        {success, nickname, avatar_url, user_id, raw?}
    """
    result: Dict[str, Any] = {
        'success': False,
        'nickname': '',
        'avatar_url': '',
        'user_id': user_id or '',
    }
    if not cookies_str:
        result['error'] = 'empty cookie'
        return result

    if self_profile:
        data_obj = {'self': True}
    else:
        if not user_id:
            result['error'] = 'user_id required'
            return result
        data_obj = {'self': False, 'userId': str(user_id)}

    data_val = json.dumps(data_obj, separators=(',', ':'), ensure_ascii=False)
    cookies = trans_cookies(cookies_str)
    token = (cookies.get('_m_h5_tk') or '').split('_')[0]
    t = str(int(time.time() * 1000))
    params = {
        'jsv': '2.7.2',
        'appKey': '34839810',
        't': t,
        'sign': generate_sign(t, token, data_val),
        'v': '1.0',
        'type': 'originaljson',
        'accountSite': 'xianyu',
        'dataType': 'json',
        'timeout': '20000',
        'api': 'mtop.idle.web.user.page.head',
        'sessionOption': 'AutoLoginOnly',
        'spm_cnt': 'a21ybx.personal.0.0',
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
                'https://h5api.m.goofish.com/h5/mtop.idle.web.user.page.head/1.0/',
                params=params,
                data={'data': data_val},
                headers=headers,
            ) as resp:
                res_json = await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f'获取用户资料失败: {e}')
        result['error'] = str(e)
        return result

    ret = res_json.get('ret') or []
    if not any('SUCCESS' in str(r) for r in ret):
        result['error'] = ';'.join(str(r) for r in ret) or 'api failed'
        logger.warning(f'用户资料 API 失败: {result["error"]}')
        return result

    data = res_json.get('data') or {}
    base_info = data.get('baseInfo') or {}
    module = data.get('module') or {}
    base = module.get('base') or {}
    avatar_obj = base.get('avatar') or {}

    nickname = (
        base.get('displayName')
        or base.get('nickname')
        or data.get('nick')
        or ''
    )
    avatar_url = ''

    def _pick_avatar(v) -> str:
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            for k in (
                'avatar', 'url', 'img', 'image', 'picUrl', 'pic_url',
                'headImg', 'head_img', 'portrait', 'src', 'big', 'medium', 'small',
            ):
                s = v.get(k)
                if isinstance(s, str) and s.strip():
                    return s.strip()
                if isinstance(s, dict):
                    nested = _pick_avatar(s)
                    if nested:
                        return nested
        return ''

    if isinstance(avatar_obj, (dict, str)):
        avatar_url = _pick_avatar(avatar_obj)
    if not avatar_url:
        for key in ('avatar', 'avatarUrl', 'headImg', 'headPic', 'portrait', 'userAvatar'):
            avatar_url = _pick_avatar(base.get(key)) or _pick_avatar(base_info.get(key)) or _pick_avatar(data.get(key))
            if avatar_url:
                break
    if not avatar_url:
        # 深挖 module 里常见头像字段
        blob_candidates = []
        for part in (base, base_info, module, data):
            if isinstance(part, dict):
                blob_candidates.append(part)
        for part in blob_candidates:
            for key in ('avatar', 'avatarUrl', 'headImg', 'userLogo', 'logo'):
                avatar_url = _pick_avatar(part.get(key))
                if avatar_url:
                    break
            if avatar_url:
                break

    if avatar_url.startswith('//'):
        avatar_url = 'https:' + avatar_url
    elif avatar_url and not avatar_url.startswith(('http://', 'https://', 'data:')):
        if avatar_url.startswith('gw.alicdn.com') or avatar_url.startswith('img.alicdn.com'):
            avatar_url = 'https://' + avatar_url

    # 仍无头像：在整棵 data 树里深挖疑似头像 URL
    if not avatar_url:
        def _walk(o, depth=0):
            if depth > 6 or o is None:
                return ''
            if isinstance(o, str):
                s = o.strip()
                if not s:
                    return ''
                low = s.lower()
                if s.startswith('//') and ('alicdn' in low or 'goofish' in low or 'taobao' in low):
                    return 'https:' + s
                if s.startswith('http') and any(
                    k in low for k in ('avatar', 'head', 'portrait', 'userlogo', 'img.alicdn', 'gw.alicdn')
                ):
                    return s
                return ''
            if isinstance(o, dict):
                # 优先常见键
                for k in ('avatar', 'avatarUrl', 'headImg', 'headPic', 'portrait', 'userLogo', 'logo', 'url', 'img'):
                    if k in o:
                        hit = _walk(o.get(k), depth + 1)
                        if hit:
                            return hit
                for v in o.values():
                    hit = _walk(v, depth + 1)
                    if hit:
                        return hit
            if isinstance(o, list):
                for v in o[:30]:
                    hit = _walk(v, depth + 1)
                    if hit:
                        return hit
            return ''

        avatar_url = _walk(data) or ''

    result.update({
        'success': True,
        'nickname': nickname.strip(),
        'avatar_url': (avatar_url or '').strip(),
        'user_id': str(base_info.get('kcUserId') or user_id or ''),
        'bio': '',
        'sold_count': '',
        'good_rate': '',
        'register_days': '',
        'register_time': '',
        'city': '',
        'raw_module_keys': list(module.keys()) if isinstance(module, dict) else [],
    })

    # 简介/签名（不同版本字段名不一致，尽量兼容）
    bio_candidates = [
        base.get('introduction'),
        base.get('intro'),
        base.get('signature'),
        base.get('desc'),
        base.get('biography'),
        base.get('userDesc'),
        base.get('personalSignature'),
        data.get('introduction'),
        data.get('signature'),
        module.get('introduction'),
        (module.get('userInfo') or {}).get('introduction') if isinstance(module.get('userInfo'), dict) else None,
        (module.get('userInfo') or {}).get('signature') if isinstance(module.get('userInfo'), dict) else None,
    ]
    for b in bio_candidates:
        if isinstance(b, str) and b.strip():
            result['bio'] = b.strip()
            break

    # 卖出/好评/入驻等（字段因版本而异，尽量从 module/base/tabs 里挖）
    def _dig_text(obj, keys):
        if not isinstance(obj, dict):
            return ''
        for k in keys:
            v = obj.get(k)
            if v is None:
                continue
            if isinstance(v, (int, float)):
                return str(v)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                for kk in ('text', 'content', 'value', 'count', 'num', 'title'):
                    if v.get(kk) not in (None, ''):
                        return str(v.get(kk)).strip()
        return ''

    pools = [base, base_info, data, module]
    for nest in ('userInfo', 'sellerInfo', 'shopInfo', 'credit', 'score', 'tabs', 'infoList', 'list'):
        n = module.get(nest) if isinstance(module, dict) else None
        if isinstance(n, dict):
            pools.append(n)
        elif isinstance(n, list):
            for it in n:
                if isinstance(it, dict):
                    pools.append(it)
                    # 形如 {title: '卖出', content: '128'}
                    title = str(it.get('title') or it.get('name') or it.get('label') or '')
                    content = str(it.get('content') or it.get('text') or it.get('value') or it.get('desc') or '')
                    if '卖出' in title or '成交' in title:
                        result['sold_count'] = result['sold_count'] or content
                    if '好评' in title:
                        result['good_rate'] = result['good_rate'] or content
                    if '来闲鱼' in title or '入驻' in title or '注册' in title:
                        result['register_days'] = result['register_days'] or content

    for p in pools:
        if not result['sold_count']:
            result['sold_count'] = _dig_text(p, (
                'soldCount', 'sold_count', 'itemSold', 'tradeCount', 'hasSold', 'sellCount', 'orderCount'
            ))
        if not result['good_rate']:
            result['good_rate'] = _dig_text(p, (
                'goodRate', 'good_rate', 'favorableRate', 'praiseRate', 'rate', 'scoreRate'
            ))
        if not result['register_days']:
            result['register_days'] = _dig_text(p, (
                'registerDays', 'register_days', 'days', 'idleDays', 'joinDays'
            ))
        if not result['register_time']:
            result['register_time'] = _dig_text(p, (
                'registerTime', 'register_time', 'createTime', 'gmtCreate'
            ))
        if not result['city']:
            result['city'] = _dig_text(p, ('city', 'ipCity', 'location', 'prov', 'province'))

    result['raw'] = {
        'base': base,
        'baseInfo': base_info,
        'module_keys': result['raw_module_keys'],
    }
    return result
