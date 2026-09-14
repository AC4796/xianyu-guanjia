# -*- coding: utf-8 -*-
"""把闲鱼官方 mtop ret / 错误原文转成用户可读提示。"""
from __future__ import annotations

from typing import Any, Dict, Optional


def extract_ret_text(payload: Any) -> str:
    """从 mtop 响应或异常字符串里抽出官方 ret 文案。"""
    if payload is None:
        return ''
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, (list, tuple)) and payload:
        return str(payload[0] or '').strip()
    if isinstance(payload, dict):
        ret = payload.get('ret')
        if isinstance(ret, (list, tuple)) and ret:
            return str(ret[0] or '').strip()
        if isinstance(ret, str) and ret.strip():
            return ret.strip()
        for k in ('message', 'msg', 'error', 'error_message', 'detail'):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return str(payload).strip()


def classify_xianyu_official(text: str) -> Dict[str, Any]:
    """
    返回:
      need_reauth: 是否应引导扫码重新授权
      code: 简码
      official: 官方原文（尽量保留）
      user_message: 展示给用户的完整专业提示
    """
    raw = (text or '').strip()
    u = raw.upper()
    need_reauth = False
    code = 'unknown'

    if any(
        k in u
        for k in (
            'FAIL_SYS_USER_VALIDATE',
            'RGV587',
            'USER_VALIDATE',
            'PUNISH',
            'CAPTCHA',
            'X5SECDATA',
        )
    ) or any(k in raw for k in ('挤爆', '滑块', '验证', '风控')):
        need_reauth = True
        code = 'risk_validate'
    elif any(
        k in u for k in ('TOKEN_EXPIRED', 'TOKEN_EXOIRED', 'SESSION_EXPIRED', 'FAIL_SYS_TOKEN')
    ) or any(k in raw for k in ('令牌过期', 'Session过期', 'SESSION过期', '登录失效')):
        need_reauth = True
        code = 'token_expired'
    elif any(k in u for k in ('LOGIN', 'AUTH', 'UNAUTHORIZED')) or '未登录' in raw:
        need_reauth = True
        code = 'need_login'

    if need_reauth and code == 'risk_validate':
        user_message = (
            '闲鱼官方风控：账号触发安全验证'
            + (f'（{raw}）' if raw else '')
            + '。请点击「重新授权」用闲鱼 App 扫码登录，刷新 Cookie 后再使用采集/消息通道。'
            ' 单纯点「重连消息通道」通常无法解除风控。'
        )
    elif need_reauth and code == 'token_expired':
        user_message = (
            '闲鱼官方提示：登录令牌/Session 已过期'
            + (f'（{raw}）' if raw else '')
            + '。请点击「重新授权」扫码登录，勿反复重连。'
        )
    elif need_reauth:
        user_message = (
            '闲鱼官方要求重新登录授权'
            + (f'（{raw}）' if raw else '')
            + '。请扫码重新授权本账号。'
        )
    elif raw:
        user_message = f'闲鱼官方返回：{raw}'
        code = 'official'
    else:
        user_message = ''
        code = 'ok'

    return {
        'need_reauth': need_reauth,
        'code': code,
        'official': raw,
        'user_message': user_message,
    }


def classify_from_payload(payload: Any) -> Dict[str, Any]:
    return classify_xianyu_official(extract_ret_text(payload))
