"""Playwright 快捷购买：打开商品页尝试点「立即购买」并可选填支付密码。"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from urllib.parse import unquote

from loguru import logger

from utils.xianyu_utils import trans_cookies


async def quick_buy_item(
    cookies_str: str,
    item_id: str,
    pay_password: Optional[str] = None,
    timeout_ms: int = 45000,
) -> Dict[str, Any]:
    """
    尝试用 Playwright 完成购买流程。
    支付宝全自动不可靠时，会返回 need_manual=True 并附上确认页 URL。
    """
    from playwright.async_api import async_playwright

    item_id = str(item_id or '').strip()
    if not item_id:
        return {'success': False, 'message': '缺少商品 ID'}

    item_url = f'https://www.goofish.com/item?id={item_id}'
    cookies = trans_cookies(cookies_str or '')
    if not cookies:
        return {'success': False, 'message': '账号 Cookie 无效，请先登录闲鱼账号'}

    pw_cookies = []
    for k, v in cookies.items():
        val = unquote(v) if k == 'tracknick' else v
        for domain in ('.goofish.com', '.taobao.com', 'www.goofish.com'):
            pw_cookies.append({'name': k, 'value': val, 'domain': domain, 'path': '/'})

    last_url = item_url
    clicked_buy = False
    filled_pwd = False

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
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
                viewport={'width': 1280, 'height': 900},
                locale='zh-CN',
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            await context.add_cookies(pw_cookies)
            page = await context.new_page()

            try:
                await page.goto(item_url, wait_until='domcontentloaded', timeout=timeout_ms)
                await page.wait_for_timeout(2000)
                last_url = page.url

                buy_labels = ('立即购买', '购买', '马上买', '去支付')
                for label in buy_labels:
                    try:
                        loc = page.get_by_text(label, exact=False).first
                        if await loc.count() > 0 and await loc.is_visible():
                            await loc.click(timeout=5000)
                            clicked_buy = True
                            await page.wait_for_timeout(2500)
                            last_url = page.url
                            break
                    except Exception:
                        continue

                if not clicked_buy:
                    # 尝试常见按钮选择器
                    for sel in (
                        'button:has-text("立即购买")',
                        'button:has-text("购买")',
                        '[class*="buy"]',
                        'a:has-text("立即购买")',
                    ):
                        try:
                            btn = page.locator(sel).first
                            if await btn.count() > 0 and await btn.is_visible():
                                await btn.click(timeout=5000)
                                clicked_buy = True
                                await page.wait_for_timeout(2500)
                                last_url = page.url
                                break
                        except Exception:
                            continue

                if not clicked_buy:
                    await browser.close()
                    return {
                        'success': False,
                        'need_manual': True,
                        'url': last_url or item_url,
                        'message': '未找到「立即购买」按钮，可能被平台反爬拦截或页面结构变化，请手动打开商品页购买。',
                    }

                # 确认下单
                for label in ('确认购买', '提交订单', '确认', '去支付宝支付', '立即支付'):
                    try:
                        loc = page.get_by_text(label, exact=False).first
                        if await loc.count() > 0 and await loc.is_visible():
                            await loc.click(timeout=4000)
                            await page.wait_for_timeout(2000)
                            last_url = page.url
                            break
                    except Exception:
                        continue

                # 支付密码
                if pay_password:
                    pwd_selectors = (
                        'input[type="password"]',
                        'input[name*="password"]',
                        'input[placeholder*="支付密码"]',
                        'input[placeholder*="密码"]',
                    )
                    for sel in pwd_selectors:
                        try:
                            inp = page.locator(sel).first
                            if await inp.count() > 0 and await inp.is_visible():
                                await inp.fill(str(pay_password), timeout=3000)
                                filled_pwd = True
                                await page.wait_for_timeout(500)
                                for label in ('确认', '支付', '完成', '提交'):
                                    try:
                                        btn = page.get_by_text(label, exact=False).first
                                        if await btn.count() > 0 and await btn.is_visible():
                                            await btn.click(timeout=3000)
                                            await page.wait_for_timeout(2000)
                                            break
                                    except Exception:
                                        continue
                                break
                        except Exception:
                            continue

                last_url = page.url
                content = ''
                try:
                    content = await page.content()
                except Exception:
                    pass

                success_hints = ('支付成功', '下单成功', '购买成功', '交易成功', '等待卖家发货')
                fail_pwd_hints = (
                    '密码错误',
                    '支付密码错误',
                    '密码不正确',
                    '密码有误',
                    '验密失败',
                    '密码验证失败',
                    'PAYMENT_PASSWORD',
                )
                if any(h in content for h in fail_pwd_hints):
                    await browser.close()
                    return {
                        'success': False,
                        'need_manual': True,
                        'password_error': True,
                        'url': last_url,
                        'message': (
                            '代发支付密码错误或校验失败。请到「系统设置 → 自动化中心」核对支付宝 6 位支付密码'
                            '（不是登录密码），保存后再试；也可在弹窗中重新填写。'
                        ),
                        'filled_password': filled_pwd,
                    }

                if any(h in content for h in success_hints) or any(
                    h in (last_url or '') for h in ('success', 'payResult', 'order-detail')
                ):
                    await browser.close()
                    return {
                        'success': True,
                        'need_manual': False,
                        'url': last_url,
                        'message': '已完成购买流程（或已进入订单成功页）。请在订单页核对实际结果。',
                        'filled_password': filled_pwd,
                    }

                # 仍在支付/确认页 → 需人工
                await browser.close()
                msg = (
                    '已点击购买并打开确认/支付页，但支付宝全自动支付不稳定。'
                    if clicked_buy
                    else '未能完成自动购买。'
                )
                if pay_password and not filled_pwd:
                    msg += ' 未检测到可填写的支付密码框（可能被平台拦截自动化）。请确认是否已开通免密/是否需手动输入。'
                elif pay_password and filled_pwd:
                    msg += ' 已尝试填写支付密码；若页面提示密码错误，请到自动化中心更新正确的 6 位支付密码后重试。'
                return {
                    'success': False,
                    'need_manual': True,
                    'url': last_url or item_url,
                    'message': msg + ' 请在浏览器中继续完成支付。',
                    'filled_password': filled_pwd,
                    'clicked_buy': clicked_buy,
                }
            except Exception as e:
                try:
                    last_url = page.url
                except Exception:
                    pass
                await browser.close()
                logger.error(f'快捷购买异常 item={item_id}: {e}')
                return {
                    'success': False,
                    'need_manual': True,
                    'url': last_url or item_url,
                    'message': f'自动化被拦截或超时：{e}。请手动打开商品页购买。',
                }
    except Exception as e:
        logger.error(f'快捷购买启动失败: {e}')
        return {
            'success': False,
            'need_manual': True,
            'url': item_url,
            'message': f'无法启动浏览器自动化：{e}',
        }
