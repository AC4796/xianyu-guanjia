#!/usr/bin/env python3
"""
闲鱼商品搜索模块
基于 Playwright 实现真实的闲鱼商品搜索功能
"""

import asyncio
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

# 修复Docker环境中的asyncio事件循环策略问题
if sys.platform.startswith('linux') or os.getenv('DOCKER_ENV'):
    try:
        # 在Linux/Docker环境中设置事件循环策略
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception as e:
        logger.warning(f"设置事件循环策略失败: {e}")

# 确保在Docker环境中使用正确的事件循环
if os.getenv('DOCKER_ENV'):
    try:
        # 强制使用SelectorEventLoop（在Docker中更稳定）
        if hasattr(asyncio, 'SelectorEventLoop'):
            loop = asyncio.SelectorEventLoop()
            asyncio.set_event_loop(loop)
    except Exception as e:
        logger.warning(f"设置SelectorEventLoop失败: {e}")

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright 未安装，将使用模拟数据")


class XianyuSearcher:
    """闲鱼商品搜索器 - 基于 Playwright"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.api_responses = []
        self.user_id = "default"  # 默认用户ID
        self.prefer_cookie_id = None  # 采集页指定账号
        self.max_items = None  # 采集目标条数，达到后停止翻页

    async def _handle_scratch_captcha_manual(self, page, max_retries=3, wait_for_completion=True):
        """人工处理刮刮乐滑块（远程控制 + 截图备份）
        
        参数:
            wait_for_completion: 是否等待用户完成验证
                - True: 等待用户完成验证（默认，用于直接处理）
                - False: 创建会话后立即返回（用于前端处理）
        """
        import random
        
        logger.warning("=" * 60)
        logger.warning("🎨 检测到刮刮乐验证，需要人工处理！")
        logger.warning("=" * 60)
        
        # 获取会话ID
        session_id = getattr(self, 'user_id', 'default')
        
        # 【新方案】启用远程控制
        use_remote_control = getattr(self, 'use_remote_control', True)
        
        if use_remote_control:
            try:
                from utils.captcha_remote_control import captcha_controller
                
                # 创建远程控制会话
                logger.warning(f"🌐 启动远程控制会话: {session_id}")
                session_info = await captcha_controller.create_session(session_id, page)
                
                # 获取控制页面URL
                import socket
                import os
                
                # 尝试多种方式获取IP
                local_ip = "localhost"
                
                # 方法1：从环境变量获取（Docker/配置文件）
                local_ip = os.getenv('SERVER_HOST') or os.getenv('PUBLIC_IP')
                
                if not local_ip:
                    # 方法2：尝试获取外网IP
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.connect(("8.8.8.8", 80))
                        local_ip = s.getsockname()[0]
                        s.close()
                        
                        # 检查是否是Docker内网IP（172.x.x.x 或 10.x.x.x）
                        if local_ip.startswith('172.') or local_ip.startswith('10.'):
                            logger.warning(f"⚠️ 检测到Docker内网IP: {local_ip}")
                            local_ip = None  # 重置，使用localhost
                    except:
                        pass
                
                if not local_ip:
                    local_ip = "localhost"
                    logger.warning("⚠️ 无法获取外网IP，使用 localhost")
                    logger.warning("💡 如果在Docker中，请设置环境变量 SERVER_HOST 为公网IP")
                
                control_url = f"http://{local_ip}:8000/api/captcha/control/{session_id}"
                
                logger.warning("=" * 60)
                logger.warning(f"🌐 远程控制已启动！")
                logger.warning(f"📱 请访问以下网址进行验证：")
                logger.warning(f"   {control_url}")
                logger.warning("=" * 60)
                logger.warning(f"💡 或直接访问: http://{local_ip}:8000/api/captcha/control")
                logger.warning(f"   然后输入会话ID: {session_id}")
                logger.warning("=" * 60)
                
                # 如果不等待完成，立即返回特殊值给调用者
                if not wait_for_completion:
                    logger.warning("⚠️ 不等待验证完成，立即返回给前端处理")
                    return 'need_captcha'  # 返回特殊值，表示需要前端处理
                
                # 等待用户完成
                logger.warning("⏳ 等待用户通过网页完成验证...")
                
                # 循环检查是否完成
                max_wait_time = 180  # 3分钟
                check_interval = 1  # 每秒检查一次
                elapsed_time = 0
                
                while elapsed_time < max_wait_time:
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
                    
                    # 检查是否完成
                    if captcha_controller.is_completed(session_id):
                        logger.success("✅ 远程验证成功！")
                        await captcha_controller.close_session(session_id)
                        return True
                    
                    # 每10秒提示一次
                    if elapsed_time % 10 == 0:
                        logger.info(f"⏳ 仍在等待...已等待 {elapsed_time} 秒")
                
                logger.error(f"❌ 远程验证超时（{max_wait_time}秒）")
                await captcha_controller.close_session(session_id)
                return False
                
            except Exception as e:
                logger.error(f"远程控制启动失败: {e}")
                logger.warning("⚠️ 降级使用传统方式")
        
        logger.error("❌ 人工验证超时，已达到最大等待时间")
        return False
    
    async def _handle_scratch_captcha_async(self, page, max_retries=15):
        """异步处理刮刮乐类型滑块"""
        import random
        
        # 保存原始page对象（用于鼠标操作）
        original_page = page
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🎨 刮刮乐滑块处理尝试 {attempt}/{max_retries}")
                
                # 重置page为原始对象
                page = original_page
                
                # 短暂等待（滑块已经存在，无需长时间等待）
                if attempt == 1:
                    await asyncio.sleep(0.3)
                else:
                    await asyncio.sleep(0.5)
                
                # 1. 快速检查刮刮乐容器（不阻塞，极短超时）
                try:
                    await page.wait_for_selector('#nocaptcha', timeout=500, state='attached')
                    logger.debug("✅ 刮刮乐容器 #nocaptcha 已加载")
                    await asyncio.sleep(0.2)  # 等待容器内部元素加载
                except:
                    # 容器未找到也继续，可能滑块还没出现
                    logger.debug("刮刮乐容器未立即加载，继续查找按钮...")
                
                # 2. 查找滑块按钮（先尝试主页面，再尝试iframe）
                button_selectors = [
                    '#scratch-captcha-btn',
                    '.button#scratch-captcha-btn',
                    'div#scratch-captcha-btn',
                    '.scratch-captcha-slider .button',
                    '#nocaptcha .button',
                    '#nocaptcha .scratch-captcha-slider .button',
                    '.button'
                ]
                
                slider_button = None
                found_in_iframe = False
                search_context = page  # 用于查找元素的上下文
                
                # 先在主页面查找（极速查找）
                for selector in button_selectors:
                    try:
                        # 先尝试等待可见（极短超时）
                        slider_button = await page.wait_for_selector(selector, timeout=800, state='visible')
                        if slider_button:
                            logger.info(f"✅ 在主页面找到刮刮乐滑块按钮（可见）: {selector}")
                            search_context = page
                            break
                    except:
                        # 如果等待可见失败，尝试只等待存在（attached）
                        try:
                            slider_button = await page.wait_for_selector(selector, timeout=300, state='attached')
                            if slider_button:
                                logger.warning(f"⚠️ 在主页面找到刮刮乐滑块按钮（不可见但存在）: {selector}")
                                search_context = page
                                break
                        except:
                            continue
                
                # 如果主页面没找到，尝试在iframe中查找（极速查找）
                if not slider_button:
                    try:
                        frames = page.frames
                        logger.debug(f"检查 {len(frames)} 个frame...")
                        for frame in frames:
                            if frame == page.main_frame:
                                continue
                            for selector in button_selectors:
                                try:
                                    slider_button = await frame.wait_for_selector(selector, timeout=500, state='visible')
                                    if slider_button:
                                        logger.info(f"✅ 在iframe中找到刮刮乐滑块按钮: {selector}")
                                        found_in_iframe = True
                                        search_context = frame  # iframe上下文用于查找
                                        break
                                except:
                                    continue
                            if slider_button:
                                break
                    except Exception as e:
                        logger.debug(f"检查iframe时出错: {e}")
                
                # 最后尝试：使用JavaScript直接查找（在search_context中）
                if not slider_button:
                    try:
                        logger.debug("尝试使用JavaScript直接查找滑块按钮...")
                        js_found = await search_context.evaluate("""
                            () => {
                                const btn = document.getElementById('scratch-captcha-btn') || 
                                           document.querySelector('#scratch-captcha-btn') ||
                                           document.querySelector('.button#scratch-captcha-btn');
                                if (btn) {
                                    return {
                                        found: true,
                                        visible: btn.offsetParent !== null,
                                        display: window.getComputedStyle(btn).display,
                                        visibility: window.getComputedStyle(btn).visibility
                                    };
                                }
                                return { found: false };
                            }
                        """)
                        
                        if js_found and js_found.get('found'):
                            logger.warning(f"⚠️ JavaScript找到按钮但Playwright无法访问: visible={js_found.get('visible')}, display={js_found.get('display')}, visibility={js_found.get('visibility')}")
                            # 尝试通过query_selector获取元素（强制操作）
                            slider_button = await search_context.query_selector('#scratch-captcha-btn')
                            if slider_button:
                                logger.info("✅ query_selector找到按钮")
                    except Exception as e:
                        logger.debug(f"JavaScript查找失败: {e}")
                
                if not slider_button:
                    logger.error("❌ 未找到刮刮乐滑块按钮（所有方法都已尝试）")
                    await asyncio.sleep(random.uniform(0.5, 1))
                    continue
                
                # 2. 获取滑块位置和大小
                button_box = await slider_button.bounding_box()
                if not button_box:
                    # 尝试使用JavaScript强制获取位置
                    try:
                        logger.warning("⚠️ 尝试使用JavaScript获取按钮位置...")
                        js_box = await search_context.evaluate("""
                            () => {
                                const btn = document.getElementById('scratch-captcha-btn');
                                if (btn) {
                                    const rect = btn.getBoundingClientRect();
                                    return {
                                        x: rect.x,
                                        y: rect.y,
                                        width: rect.width,
                                        height: rect.height
                                    };
                                }
                                return null;
                            }
                        """)
                        if js_box:
                            logger.info(f"✅ JavaScript获取到按钮位置: {js_box}")
                            button_box = js_box
                        else:
                            logger.error("❌ JavaScript也无法获取滑块按钮位置")
                            await asyncio.sleep(random.uniform(0.5, 1))
                            continue
                    except Exception as e:
                        logger.error(f"❌ 无法获取滑块按钮位置: {e}")
                        await asyncio.sleep(random.uniform(0.5, 1))
                        continue
                
                # 3. 计算滑动距离（25-35%）
                # 假设轨道宽度约为300px（可以根据实际调整）
                estimated_track_width = 300
                scratch_ratio = random.uniform(0.25, 0.35)
                slide_distance = estimated_track_width * scratch_ratio
                
                logger.warning(f"🎨 刮刮乐模式：计划滑动{scratch_ratio*100:.1f}%距离 ({slide_distance:.2f}px)")
                
                # 4. 执行滑动
                start_x = button_box['x'] + button_box['width'] / 2
                start_y = button_box['y'] + button_box['height'] / 2
                
                # 移动到滑块（优化等待时间）
                await page.mouse.move(start_x, start_y)
                await asyncio.sleep(random.uniform(0.1, 0.2))
                
                # 按下鼠标
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.1))
                
                # 模拟人类化滑动轨迹（加快速度）
                steps = random.randint(10, 15)
                for i in range(steps):
                    progress = (i + 1) / steps
                    current_distance = slide_distance * progress
                    
                    # 添加Y轴抖动
                    y_jitter = random.uniform(-2, 2)
                    
                    await page.mouse.move(
                        start_x + current_distance,
                        start_y + y_jitter
                    )
                    await asyncio.sleep(random.uniform(0.005, 0.015))
                
                # 5. 在目标位置停顿观察（缩短时间）
                pause_duration = random.uniform(0.2, 0.3)
                logger.warning(f"🎨 在目标位置停顿{pause_duration:.2f}秒观察...")
                await asyncio.sleep(pause_duration)
                
                # 6. 释放鼠标
                await page.mouse.up()
                await asyncio.sleep(random.uniform(0.3, 0.5))
                
                # 7. 检查是否成功（检查滑块frame是否消失）
                try:
                    # 等待验证结果
                    await asyncio.sleep(0.8)
                    
                    # 检查主页面的滑块容器
                    captcha_in_main = await page.query_selector('#nocaptcha')
                    main_visible = False
                    if captcha_in_main:
                        try:
                            main_visible = await captcha_in_main.is_visible()
                        except:
                            main_visible = False
                    
                    # 检查iframe中的滑块
                    iframe_visible = False
                    try:
                        frames = page.frames
                        for frame in frames:
                            if frame != page.main_frame:
                                captcha_in_iframe = await frame.query_selector('#nocaptcha')
                                if captcha_in_iframe:
                                    try:
                                        if await captcha_in_iframe.is_visible():
                                            iframe_visible = True
                                            break
                                    except:
                                        pass
                    except:
                        pass
                    
                    # 判断成功：主页面和iframe都没有可见的滑块
                    if not main_visible and not iframe_visible:
                        logger.success(f"✅ 刮刮乐验证成功！滑块已消失（第{attempt}次尝试）")
                        return True
                    else:
                        if main_visible:
                            logger.warning(f"⚠️ 主页面滑块仍可见，继续重试...")
                        if iframe_visible:
                            logger.warning(f"⚠️ iframe滑块仍可见，继续重试...")
                except Exception as e:
                    logger.warning(f"⚠️ 检查验证结果时出错: {e}，继续重试...")
                
            except Exception as e:
                logger.error(f"❌ 刮刮乐处理异常: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(random.uniform(0.5, 1))
                continue
        
        logger.error(f"❌ 刮刮乐验证失败，已达到最大重试次数 {max_retries}")
        return False
    
    async def handle_slider_verification(self, page, context=None, browser=None, playwright=None, max_retries=5):
        """
        通用的滑块验证处理方法
        
        参数:
            page: Playwright 页面对象（必需）
            context: Playwright 上下文对象（可选，如果不传则使用 self.context）
            browser: Playwright 浏览器对象（可选，如果不传则使用 self.browser）
            playwright: Playwright 实例（可选，如果不传则使用 self.playwright）
            max_retries: 最大重试次数，默认5次
            
        返回:
            bool: True表示成功（包括没有滑块或滑块验证成功），False表示失败
        """
        try:
            # 等待页面加载滑块元素（优化等待时间）
            await asyncio.sleep(1)
            logger.info("🔍 开始检测滑块验证...")
            
            # 使用传入的对象或实例属性
            context = context or self.context
            browser = browser or self.browser
            playwright = playwright or getattr(self, 'playwright', None)
            
            # 【调试】打印页面HTML内容，查找滑块相关关键词
            try:
                page_content = await page.content()
                has_captcha_keyword = any(keyword in page_content.lower() for keyword in [
                    'nocaptcha', 'scratch-captcha', 'captcha', 'slider', '滑块', '验证'
                ])
                if has_captcha_keyword:
                    logger.warning("⚠️ 页面HTML中包含滑块相关关键词")
                    # 保存页面内容用于调试
                    if 'nocaptcha' in page_content or 'scratch-captcha' in page_content:
                        logger.warning("🎯 检测到刮刮乐类型滑块特征词！")
                else:
                    logger.info("✅ 页面HTML中未发现滑块关键词")
            except Exception as e:
                logger.debug(f"检查页面内容时出错: {e}")
            
            # 检测滑块元素（支持多种类型的滑块）
            slider_selectors = [
                # 阿里云盾 nc 系列滑块
                '#nc_1_n1z',
                '.nc-container',
                '.nc_scale',
                '.nc-wrapper',
                '[class*="nc_"]',
                '[id*="nc_"]',
                # 刮刮乐 (scratch-captcha) 类型滑块
                '#nocaptcha',
                '.scratch-captcha-container',
                '.scratch-captcha-slider',
                '#scratch-captcha-btn',
                '[class*="scratch-captcha"]',
                'div[id="nocaptcha"]',
                'div.scratch-captcha-container',
                # 其他常见滑块类型
                '.captcha-slider',
                '.slider-captcha',
                '[class*="captcha"]',
                '[id*="captcha"]'
            ]
            
            has_slider = False
            detected_selector = None
            found_elements = []
            
            for selector in slider_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        found_elements.append(selector)
                        is_visible = await element.is_visible()
                        logger.debug(f"找到元素 {selector}，可见性: {is_visible}")
                        if is_visible:
                            logger.info(f"✅ 检测到滑块验证元素: {selector}")
                            has_slider = True
                            detected_selector = selector
                            break
                except Exception as e:
                    logger.debug(f"选择器 {selector} 检测出错: {e}")
                    continue
            
            # 输出调试信息
            if found_elements:
                logger.warning(f"🔍 找到以下滑块元素（但可能不可见）: {', '.join(found_elements)}")
                # 如果找到了元素但不可见，强制认为有滑块
                if not has_slider and any('captcha' in sel.lower() or 'slider' in sel.lower() for sel in found_elements):
                    logger.warning("⚠️ 检测到滑块元素但不可见，仍然尝试处理")
                    has_slider = True
                    detected_selector = found_elements[0]
            else:
                logger.debug("未找到任何滑块选择器匹配的元素")
            
            # 【额外检测】检查 iframe 中的滑块
            if not has_slider:
                try:
                    frames = page.frames
                    logger.debug(f"检测到 {len(frames)} 个 frame")
                    for frame in frames:
                        if frame != page.main_frame:
                            try:
                                iframe_content = await frame.content()
                                # 更精确的刮刮乐检测：必须包含明确特征
                                has_scratch_features = 'scratch-captcha' in iframe_content or \
                                                      ('nocaptcha' in iframe_content and 'scratch' in iframe_content)
                                if has_scratch_features:
                                    logger.warning("🎯 在 iframe 中检测到刮刮乐滑块！")
                                    has_slider = True
                                    detected_selector = "iframe-scratch-captcha"
                                    break
                            except:
                                continue
                except Exception as e:
                    logger.debug(f"检查 iframe 时出错: {e}")
            
            # 如果没有检测到滑块，直接返回成功
            if not has_slider:
                logger.info("✅ 未检测到滑块验证，继续执行")
                return True
            
            # 检测到滑块，开始处理
            logger.warning(f"⚠️ 检测到滑块验证（{detected_selector}），开始处理...")
            
            # 检测是否为刮刮乐类型（更精确的判断）
            is_scratch_captcha = False
            
            # 明确的刮刮乐特征
            if 'scratch' in detected_selector.lower():
                is_scratch_captcha = True
            # 如果选择器是 #nocaptcha 但不是 nc 系列的标准滑块，则进一步检查
            elif detected_selector in ['#nocaptcha', 'iframe-scratch-captcha']:
                try:
                    page_html = await page.content()
                    # 检查是否有刮刮乐的明确特征
                    has_scratch_features = 'scratch-captcha' in page_html or \
                                          ('Release the slider' in page_html) or \
                                          ('fully appears' in page_html)
                    is_scratch_captcha = has_scratch_features
                except:
                    is_scratch_captcha = False
            
            if is_scratch_captcha:
                logger.warning("🎨 检测到刮刮乐类型滑块")
                
                # 人工处理模式 - 等待用户完成验证
                logger.warning("⚠️ 刮刮乐需要人工处理，等待验证完成")
                slider_success = await self._handle_scratch_captcha_manual(page, max_retries=3, wait_for_completion=True)
            else:
                actual_max_retries = max_retries
                slider_success = None
            
            try:
                # 刮刮乐已经处理过了，直接检查结果
                if is_scratch_captcha:
                    pass  # slider_success 已经在上面设置
                else:
                    # 普通滑块：使用 XianyuSliderStealth（同步API）
                    from utils.xianyu_slider_stealth import XianyuSliderStealth
                    
                    # 创建滑块处理实例
                    slider_handler = XianyuSliderStealth(
                        user_id=getattr(self, 'user_id', 'default'),
                        enable_learning=True,
                        headless=True
                    )
                    
                    # 将现有的浏览器对象传递给滑块处理器（复用现有浏览器）
                    slider_handler.page = page
                    slider_handler.context = context
                    slider_handler.browser = browser
                    slider_handler.playwright = playwright
                    
                    # 调用滑块处理方法
                    logger.info(f"🎯 开始处理滑块验证（最多尝试 {actual_max_retries} 次）...")
                    slider_success = slider_handler.solve_slider(max_retries=actual_max_retries)
                    
                    # 清除引用，防止 XianyuSliderStealth 尝试关闭我们的浏览器
                    slider_handler.page = None
                    slider_handler.context = None
                    slider_handler.browser = None
                    slider_handler.playwright = None
                
                if slider_success:
                    logger.success("✅ 滑块验证成功！")
                    return True
                else:
                    logger.error("❌ 滑块验证失败")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ 滑块验证处理异常: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                
                # 确保清除引用
                try:
                    if 'slider_handler' in locals():
                        slider_handler.page = None
                        slider_handler.context = None
                        slider_handler.browser = None
                        slider_handler.playwright = None
                except:
                    pass
                
                return False
                
        except Exception as e:
            logger.error(f"❌ 滑块检测过程异常: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def safe_get(self, data, *keys, default="暂无"):
        """安全获取嵌套字典值"""
        for key in keys:
            try:
                data = data[key]
            except (KeyError, TypeError, IndexError):
                return default
        return data

    async def get_first_valid_cookie(self):
        """获取有效 cookie；优先使用 prefer_cookie_id（采集页当前账号）"""
        try:
            from db_manager import db_manager

            cookies = db_manager.get_all_cookies()
            prefer = getattr(self, 'prefer_cookie_id', None)
            if prefer and prefer in cookies and len(cookies.get(prefer) or '') > 50:
                logger.info(f"使用指定 cookie: {prefer}")
                return {'id': prefer, 'value': cookies[prefer]}

            for cookie_id, cookie_value in cookies.items():
                if len(cookie_value) > 50:
                    logger.info(f"找到有效cookie: {cookie_id}")
                    return {
                        'id': cookie_id,
                        'value': cookie_value
                    }

            return None

        except Exception as e:
            logger.error(f"获取cookie失败: {str(e)}")
            return None

    async def search_multiple_pages_via_api(self, keyword: str, total_pages: int = 1) -> Dict[str, Any]:
        """通过在线账号 mtop 直连翻页（禁止 Playwright，避免采集一直转圈）"""
        cookie_data = await self.get_first_valid_cookie()
        if not cookie_data:
            return {'items': [], 'total': 0, 'error': '无有效 Cookie', 'source': 'api'}

        prefer = str(getattr(self, 'prefer_cookie_id', None) or cookie_data.get('id') or '')
        live = None
        created_tmp = False
        cookies_str = cookie_data.get('value') or ''
        try:
            from XianyuAutoAsync import XianyuLive
            # 只借在线号最新 Cookie，绝不复用其 aiohttp session（会 Timeout context / 卡死采集）
            online = XianyuLive.get_instance(prefer)
            if online and getattr(online, 'cookies_str', None):
                cookies_str = online.cookies_str
            live = XianyuLive(cookies_str, cookie_id=prefer, bind_instance=False)
            await asyncio.wait_for(live.create_session(), timeout=8.0)
            created_tmp = True
        except Exception as e:
            logger.warning(f'创建临时搜索 live 失败: {e}')
            live = None

        if not live or not hasattr(live, '_post_mtop'):
            return {
                'items': [],
                'total': 0,
                'error': '账号未在线，无法采集。请先保持消息通道在线后再试。',
                'source': 'api',
            }

        max_items = getattr(self, 'max_items', None)
        rows_per_page = 30
        all_items: List[Dict[str, Any]] = []
        seen_ids = set()
        fetched_pages = 0
        last_error = ''
        empty_streak = 0
        dup_streak = 0
        validate_retried = False

        page_budget = max(1, min(20, int(total_pages or 1)))
        if max_items:
            page_budget = max(page_budget, min(20, (int(max_items) + rows_per_page - 1) // rows_per_page + 2))

        try:
            page_num = 1
            while page_num <= page_budget:
                if max_items and len(all_items) >= int(max_items):
                    break
                payload = {
                    'pageNumber': page_num,
                    'keyword': keyword,
                    'fromFilter': False,
                    'rowsPerPage': rows_per_page,
                    'sortValue': '',
                    'sortField': '',
                    'customDistance': '',
                    'gps': '',
                    'propValueStr': {},
                    'customGps': '',
                    'searchReqFromPage': 'pcSearch',
                    'extraFilterValue': '{}',
                    'userPositionJson': '{}',
                }
                try:
                    res_json = await asyncio.wait_for(
                        live._post_mtop(
                            'mtop.taobao.idlemtopsearch.pc.search',
                            '1.0',
                            payload,
                            spm_cnt='a21ybx.search.0.0',
                        ),
                        timeout=12.0,
                    )
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f'API 搜索第 {page_num} 页异常: {e}')
                    empty_streak += 1
                    if empty_streak >= 2:
                        break
                    await asyncio.sleep(0.3)
                    page_num += 1
                    continue

                ret = ((res_json or {}).get('ret') or [''])[0]
                ret_u = str(ret).upper()
                if 'SUCCESS' not in ret_u:
                    last_error = str(ret)
                    logger.warning(f'API 搜索失败 page={page_num}: {ret}')
                    need_captcha = ('USER_VALIDATE' in ret_u) or ('RGV587' in ret_u) or ('挤爆' in str(ret))
                    if need_captcha:
                        # 不再弹自动滑块（用户手动也常过不去）；按官方原文引导首页扫码重新授权
                        try:
                            from utils.xy_official_msg import classify_from_payload
                            from db_manager import db_manager
                            info = classify_from_payload(res_json)
                            last_error = info.get('user_message') or last_error
                            prefer_id = str(getattr(self, 'prefer_cookie_id', None) or prefer or '')
                            if prefer_id:
                                db_manager.add_risk_control_log(
                                    cookie_id=prefer_id,
                                    event_type='official_risk',
                                    event_description=info.get('user_message') or '采集触发闲鱼官方风控',
                                    processing_result=str(ret),
                                    processing_status='failed',
                                    error_message=str(ret),
                                )
                            try:
                                online = None
                                from XianyuAutoAsync import XianyuLive
                                online = XianyuLive.get_instance(prefer_id)
                                if online:
                                    online.last_official_error = str(ret)
                                    online.last_token_refresh_error = str(ret)
                            except Exception:
                                pass
                        except Exception as le:
                            logger.warning(f'记录采集风控失败: {le}')
                        break
                    if (not validate_retried) and any(k in ret_u for k in ('TOKEN', 'SESSION')):
                        validate_retried = True
                        await asyncio.sleep(0.3)
                        continue
                    break

                data_obj = ((res_json or {}).get('data') or {}) if isinstance(res_json, dict) else {}
                raw_list = data_obj.get('resultList') or data_obj.get('cardList') or []
                if not raw_list:
                    empty_streak += 1
                    logger.info(f'API 第 {page_num} 页无结果（连续空页 {empty_streak}）')
                    if empty_streak >= 2:
                        break
                    await asyncio.sleep(0.2)
                    page_num += 1
                    continue
                empty_streak = 0

                page_new = 0
                for item in raw_list:
                    try:
                        parsed = await self._parse_real_item(item)
                        if not parsed:
                            continue
                        iid = str(parsed.get('item_id') or '')
                        if iid in ('未知ID', '暂无'):
                            iid = ''
                        if iid and iid in seen_ids:
                            continue
                        if iid:
                            seen_ids.add(iid)
                        all_items.append(parsed)
                        page_new += 1
                        if max_items and len(all_items) >= int(max_items):
                            break
                    except Exception:
                        continue

                fetched_pages = page_num
                logger.info(f'API 第 {page_num} 页新增 {page_new} 条，累计 {len(all_items)}')
                if page_new == 0:
                    dup_streak += 1
                    if dup_streak >= 2:
                        break
                else:
                    dup_streak = 0
                page_num += 1
                await asyncio.sleep(0.15)
        finally:
            if created_tmp and live:
                try:
                    await live.close_session()
                except Exception:
                    pass

        incomplete = bool(max_items and len(all_items) < int(max_items))
        err = last_error if not all_items else None
        if err:
            eu = str(err).upper()
            if 'USER_VALIDATE' in eu or 'RGV587' in eu or '挤爆' in str(err):
                try:
                    from utils.xy_official_msg import classify_xianyu_official
                    err = classify_xianyu_official(str(err)).get('user_message') or err
                except Exception:
                    err = (
                        '闲鱼官方风控：账号触发安全验证。请回首页点击「重新授权」扫码登录后再采集。'
                    )
            elif 'TOKEN' in eu or 'SESSION' in eu or '令牌' in str(err):
                err = '账号令牌失效，请保持消息通道在线后重试。'
        return {
            'items': all_items,
            'total': len(all_items),
            'has_more': incomplete,
            'is_real_data': True,
            'source': 'mtop-api',
            'fetched_pages': fetched_pages or (1 if all_items else 0),
            'incomplete': incomplete,
            'error': err,
        }

    async def _search_multiple_pages_via_api_legacy_unused(self, keyword: str, total_pages: int = 1) -> Dict[str, Any]:
        """旧 aiohttp 直连（保留不调用）"""
        import aiohttp
        from utils.xianyu_utils import generate_sign, trans_cookies

        cookie_data = await self.get_first_valid_cookie()
        if not cookie_data:
            return {'items': [], 'total': 0, 'error': '无有效 Cookie', 'source': 'api'}

        cookies_str = cookie_data.get('value') or ''
        prefer = getattr(self, 'prefer_cookie_id', None) or cookie_data.get('id')
        try:
            from XianyuAutoAsync import XianyuLive
            live = XianyuLive.get_instance(str(prefer or ''))
            if live and getattr(live, 'cookies_str', None):
                cookies_str = live.cookies_str
        except Exception:
            pass
        cookies = trans_cookies(cookies_str)
        max_items = getattr(self, 'max_items', None)
        rows_per_page = 30
        all_items: List[Dict[str, Any]] = []
        seen_ids = set()
        fetched_pages = 0
        last_error = ''
        empty_streak = 0
        dup_streak = 0

        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.goofish.com',
            'referer': 'https://www.goofish.com/',
            'user-agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            ),
            'cookie': cookies_str,
        }

        # 目标条数时多翻几页，避免因重复/空页提前停导致少采
        page_budget = max(1, int(total_pages))
        if max_items:
            page_budget = max(page_budget, int(max_items) // rows_per_page + 8)

        async with aiohttp.ClientSession(headers=headers) as session:
            for page_num in range(1, page_budget + 1):
                if max_items and len(all_items) >= int(max_items):
                    break
                payload = {
                    'pageNumber': page_num,
                    'keyword': keyword,
                    'fromFilter': False,
                    'rowsPerPage': rows_per_page,
                    'sortValue': '',
                    'sortField': '',
                    'customDistance': '',
                    'gps': '',
                    'propValueStr': {},
                    'customGps': '',
                    'searchReqFromPage': 'pcSearch',
                    'extraFilterValue': '{}',
                    'userPositionJson': '{}',
                }
                data_val = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
                t = str(int(time.time() * 1000))
                token = (cookies.get('_m_h5_tk') or '').split('_')[0]
                sign = generate_sign(t, token, data_val)
                params = {
                    'jsv': '2.7.2',
                    'appKey': '34839810',
                    't': t,
                    'sign': sign,
                    'v': '1.0',
                    'type': 'originaljson',
                    'accountSite': 'xianyu',
                    'dataType': 'json',
                    'timeout': '20000',
                    'api': 'mtop.taobao.idlemtopsearch.pc.search',
                    'sessionOption': 'AutoLoginOnly',
                    'spm_cnt': 'a21ybx.search.0.0',
                }
                try:
                    async with session.post(
                        'https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/',
                        params=params,
                        data={'data': data_val},
                        timeout=aiohttp.ClientTimeout(total=25),
                    ) as resp:
                        # 同步 token（优先用 CookieJar）
                        try:
                            for c in session.cookie_jar:
                                try:
                                    cookies[c.key] = c.value
                                except Exception:
                                    pass
                            if cookies:
                                cookies_str = '; '.join(f'{k}={v}' for k, v in cookies.items())
                                session.headers['cookie'] = cookies_str
                        except Exception:
                            pass

                        if resp.status != 200:
                            last_error = f'HTTP {resp.status}'
                            logger.warning(f'API 搜索第 {page_num} 页 HTTP {resp.status}')
                            empty_streak += 1
                            if empty_streak >= 3:
                                break
                            continue
                        res_json = await resp.json(content_type=None)
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f'API 搜索第 {page_num} 页异常: {e}')
                    empty_streak += 1
                    if empty_streak >= 3:
                        break
                    await asyncio.sleep(0.5)
                    continue

                ret = (res_json.get('ret') or [''])[0]
                if 'TOKEN' in str(ret).upper() or 'FAIL_SYS' in str(ret).upper():
                    last_error = str(ret)
                    logger.warning(f'API 搜索鉴权失败 page={page_num}: {ret}')
                    # 只对首页重试一次（token 已刷新）
                    if page_num == 1 and not getattr(self, '_api_token_retried', False):
                        self._api_token_retried = True
                        continue
                    break

                raw_list = (res_json.get('data') or {}).get('resultList') or []
                if not raw_list:
                    empty_streak += 1
                    logger.info(f'API 第 {page_num} 页无结果（连续空页 {empty_streak}）')
                    # 连续 3 空页才认定真没了，避免偶发空页少采
                    if empty_streak >= 3:
                        break
                    await asyncio.sleep(0.35)
                    continue
                empty_streak = 0

                page_new = 0
                for item in raw_list:
                    try:
                        parsed = await self._parse_real_item(item)
                        if not parsed:
                            continue
                        iid = str(parsed.get('item_id') or '')
                        if iid and iid in seen_ids:
                            continue
                        if iid:
                            seen_ids.add(iid)
                        all_items.append(parsed)
                        page_new += 1
                        if max_items and len(all_items) >= int(max_items):
                            break
                    except Exception:
                        continue

                fetched_pages = page_num
                logger.info(f'API 第 {page_num} 页新增 {page_new} 条，累计 {len(all_items)}')
                if page_new == 0:
                    dup_streak += 1
                    # 连续 3 页全是重复才停，避免过早截断
                    if dup_streak >= 3:
                        break
                else:
                    dup_streak = 0
                # 轻微间隔，降低风控；远小于 Playwright 的数秒等待
                await asyncio.sleep(0.25)

        incomplete = bool(max_items and len(all_items) < int(max_items))
        return {
            'items': all_items,
            'total': len(all_items),
            'has_more': incomplete,
            'is_real_data': True,
            'source': 'mtop-api',
            'fetched_pages': fetched_pages or (1 if all_items else 0),
            'incomplete': incomplete,
            'error': last_error if not all_items else None,
        }

    async def set_browser_cookies(self, cookie_value: str):
        """设置浏览器cookies"""
        try:
            if not cookie_value:
                return False

            # 解析cookie字符串
            cookies = []
            for cookie_pair in cookie_value.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    name, value = cookie_pair.split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.goofish.com',
                        'path': '/'
                    })

            # 设置cookies到浏览器
            await self.context.add_cookies(cookies)
            logger.info(f"成功设置 {len(cookies)} 个cookies到浏览器")
            return True

        except Exception as e:
            logger.error(f"设置浏览器cookies失败: {str(e)}")
            return False

    async def init_browser(self):
        """初始化浏览器（使用持久化上下文，保留缓存和cookies）"""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright 未安装，无法使用真实搜索功能")

        if not self.browser:
            playwright = await async_playwright().start()
            
            # 设置持久化数据目录（保存缓存、cookies等）
            import tempfile
            user_data_dir = os.path.join(tempfile.gettempdir(), 'xianyu_browser_cache')
            os.makedirs(user_data_dir, exist_ok=True)
            logger.info(f"使用持久化数据目录（保留缓存）: {user_data_dir}")
            
            # 简化的浏览器启动参数，避免冲突
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--disable-extensions',
                '--disable-default-apps',
                '--no-default-browser-check',
                # 中文语言设置
                '--lang=zh-CN',
                '--accept-lang=zh-CN,zh,en-US,en'
            ]

            # 只在确实是Docker环境时添加额外参数
            if os.getenv('DOCKER_ENV') == 'true':
                browser_args.extend([
                    '--disable-gpu',
                    # 移除--single-process参数，使用多进程模式提高稳定性
                    # '--single-process'  # 注释掉，避免崩溃
                ])

            logger.info("正在启动浏览器（中文模式，持久化缓存）...")
            
            # 使用 launch_persistent_context 实现跨会话的缓存持久化
            # 这样通过一次滑块验证后，下次搜索可以复用缓存，避免再次出现滑块
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir,  # 第一个参数是用户数据目录，用于持久化
                headless=True,  # 无头模式，后台运行
                args=browser_args,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720},
                locale='zh-CN',  # 设置语言为中文
                # 持久化上下文会自动保存和加载：
                # - Cookies
                # - 缓存
                # - LocalStorage
                # - SessionStorage
                # - 其他浏览器状态
            )
            
            # launch_persistent_context 返回的是 context，不是 browser
            # 需要通过 context.browser 获取 browser 对象
            self.browser = self.context.browser

            logger.info("浏览器启动成功（持久化上下文已创建）...")

            logger.info("创建页面...")
            self.page = await self.context.new_page()

            logger.info("浏览器初始化完成（缓存将持久化保存）")

    async def close_browser(self):
        """关闭浏览器（持久化上下文会自动保存缓存和cookies）"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            # 注意：使用 persistent_context 时，关闭 context 会自动保存所有数据
            if self.context:
                await self.context.close()
                self.context = None
            # persistent_context 的 browser 会在 context 关闭时自动关闭
            # 不需要单独关闭 browser
            self.browser = None
            logger.debug("商品搜索器浏览器已关闭（缓存已保存）")
        except Exception as e:
            logger.warning(f"关闭商品搜索器浏览器时出错: {e}")

    async def search_via_playwright_fast(
        self, keyword: str, max_items: Optional[int] = None
    ) -> Dict[str, Any]:
        """短时浏览器兜底：直达搜索页拦截 API，禁止 networkidle，不写 Cookie 入库。"""
        if not PLAYWRIGHT_AVAILABLE:
            return {'items': [], 'total': 0, 'error': 'Playwright 不可用', 'source': 'playwright-fast'}

        import urllib.parse

        all_items: List[Dict[str, Any]] = []
        seen = set()
        last_error = ''
        try:
            await asyncio.wait_for(self.init_browser(), timeout=15.0)
            cookie_data = await self.get_first_valid_cookie()
            if not cookie_data:
                return {'items': [], 'total': 0, 'error': '无有效 Cookie', 'source': 'playwright-fast'}

            # 优先用在线实例最新 Cookie（只读，不回写）
            cookies_str = cookie_data.get('value') or ''
            try:
                from XianyuAutoAsync import XianyuLive
                online = XianyuLive.get_instance(str(cookie_data.get('id') or ''))
                if online and getattr(online, 'cookies_str', None):
                    cookies_str = online.cookies_str
            except Exception:
                pass

            self.api_responses = []

            async def on_response(response):
                if 'mtop.taobao.idlemtopsearch.pc.search' not in response.url:
                    return
                try:
                    if response.status != 200:
                        return
                    result_json = await response.json()
                    self.api_responses.append(result_json)
                    for item in ((result_json.get('data') or {}).get('resultList') or []):
                        try:
                            parsed = await self._parse_real_item(item)
                            if not parsed:
                                continue
                            iid = str(parsed.get('item_id') or '')
                            if iid in ('未知ID', '暂无'):
                                iid = ''
                            if iid and iid in seen:
                                continue
                            if iid:
                                seen.add(iid)
                            all_items.append(parsed)
                        except Exception:
                            continue
                except Exception:
                    return

            self.page.on('response', on_response)
            await self.page.goto('https://www.goofish.com/', timeout=20000, wait_until='domcontentloaded')
            await self.set_browser_cookies(cookies_str)
            await self.page.reload(timeout=20000, wait_until='domcontentloaded')
            await asyncio.sleep(0.8)

            q = urllib.parse.quote(keyword or '')
            url = f'https://www.goofish.com/search?q={q}'
            await self.page.goto(url, timeout=20000, wait_until='domcontentloaded')

            # 等 API；若出滑块则自动处理一次
            deadline = time.time() + 18.0
            slider_done = False
            while time.time() < deadline and (not max_items or len(all_items) < int(max_items)):
                if all_items:
                    break
                if not slider_done:
                    try:
                        ok = await asyncio.wait_for(
                            self.handle_slider_verification(
                                page=self.page,
                                context=self.context,
                                browser=self.browser,
                                playwright=getattr(self, 'playwright', None),
                                max_retries=2,
                            ),
                            timeout=12.0,
                        )
                        slider_done = True
                        if ok:
                            await asyncio.sleep(1.0)
                            continue
                    except Exception:
                        slider_done = True
                await asyncio.sleep(0.4)

            # 从已捕获响应里再解析一次（防止监听时序漏掉）
            for result_json in list(self.api_responses or []):
                ret = ((result_json or {}).get('ret') or [''])[0]
                if 'SUCCESS' not in str(ret).upper():
                    last_error = str(ret)
                    continue
                for item in ((result_json.get('data') or {}).get('resultList') or []):
                    try:
                        parsed = await self._parse_real_item(item)
                        if not parsed:
                            continue
                        iid = str(parsed.get('item_id') or '')
                        if iid in ('未知ID', '暂无'):
                            iid = ''
                        if iid and iid in seen:
                            continue
                        if iid:
                            seen.add(iid)
                        all_items.append(parsed)
                        if max_items and len(all_items) >= int(max_items):
                            break
                    except Exception:
                        continue

            if max_items and all_items:
                all_items = all_items[: int(max_items)]

            if not all_items:
                eu = str(last_error).upper()
                if 'USER_VALIDATE' in eu or 'RGV587' in eu:
                    last_error = '闲鱼风控验证未自动通过，请稍后再试（系统会自动过滑块，无需扫码）'
                return {
                    'items': [],
                    'total': 0,
                    'error': last_error or '浏览器未拦截到搜索结果',
                    'source': 'playwright-fast',
                }

            return {
                'items': all_items,
                'total': len(all_items),
                'is_real_data': True,
                'source': 'playwright-fast',
                'fetched_pages': 1,
            }
        except Exception as e:
            logger.warning(f'Playwright 快速搜索失败: {e}')
            return {'items': [], 'total': 0, 'error': str(e), 'source': 'playwright-fast'}

    async def search_items(self, keyword: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        搜索闲鱼商品 - 使用 Playwright 获取真实数据

        Args:
            keyword: 搜索关键词
            page: 页码，从1开始
            page_size: 每页数量

        Returns:
            搜索结果字典，包含items列表和总数
        """
        try:
            if not PLAYWRIGHT_AVAILABLE:
                logger.error("Playwright 不可用，无法获取真实数据")
                return {
                    'items': [],
                    'total': 0,
                    'error': 'Playwright 不可用，无法获取真实数据'
                }

            logger.info(f"使用 Playwright 搜索闲鱼商品: 关键词='{keyword}', 页码={page}, 每页={page_size}")

            await self.init_browser()

            # 清空之前的API响应
            self.api_responses = []
            data_list = []

            # 设置API响应监听器
            async def on_response(response):
                """处理API响应，解析数据"""
                if "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search" in response.url:
                    try:
                        # 检查响应状态
                        if response.status != 200:
                            logger.warning(f"API响应状态异常: {response.status}")
                            return

                        # 安全地获取响应内容
                        try:
                            result_json = await response.json()
                        except Exception as json_error:
                            logger.warning(f"无法解析响应JSON: {str(json_error)}")
                            return

                        self.api_responses.append(result_json)
                        logger.info(f"捕获到API响应，URL: {response.url}")

                        items = result_json.get("data", {}).get("resultList", [])
                        logger.info(f"从API获取到 {len(items)} 条原始数据")

                        for item in items:
                            try:
                                parsed_item = await self._parse_real_item(item)
                                if parsed_item:
                                    data_list.append(parsed_item)
                            except Exception as parse_error:
                                logger.warning(f"解析单个商品失败: {str(parse_error)}")
                                continue

                    except Exception as e:
                        logger.warning(f"响应处理异常: {str(e)}")

            try:
                # 获取并设置cookies进行登录
                logger.info("正在获取有效的cookies账户...")
                cookie_data = await self.get_first_valid_cookie()
                if not cookie_data:
                    raise Exception("未找到有效的cookies账户，请先在Cookie管理中添加有效的闲鱼账户")

                logger.info(f"使用账户: {cookie_data.get('id', 'unknown')}")

                logger.info("正在访问闲鱼首页...")
                await self.page.goto("https://www.goofish.com", timeout=30000)

                # 设置cookies进行登录
                logger.info("正在设置cookies进行登录...")
                cookie_success = await self.set_browser_cookies(cookie_data.get('value', ''))
                if not cookie_success:
                    logger.warning("设置cookies失败，将以未登录状态继续")
                else:
                    logger.info("✅ cookies设置成功，已登录")
                    # 刷新页面以应用cookies
                    await self.page.reload()
                    await asyncio.sleep(2)
               
                    

                await self.page.wait_for_load_state("domcontentloaded", timeout=10000)

                logger.info(f"正在搜索关键词: {keyword}")
                await self.page.fill('input[class*="search-input"]', keyword)

                # 注册响应监听
                self.page.on("response", on_response)

                await self.page.click('button[type="submit"]')
                                  
                await self.page.wait_for_load_state("domcontentloaded", timeout=15000)

                # 等待第一页API响应（缩短等待时间）
                logger.info("等待第一页API响应...")
                await asyncio.sleep(2)
                
                # 尝试处理弹窗
                try:
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                except:
                    pass
                # 【核心】检测并处理滑块验证 → 使用公共方法
                logger.info(f"检测是否有滑块验证...")
                slider_result = await self.handle_slider_verification(
                    page=self.page,
                    context=self.context,
                    browser=self.browser,
                    playwright=getattr(self, 'playwright', None),
                    max_retries=5
                )
                
                if not slider_result:
                    logger.error(f"❌ 滑块验证失败，搜索终止")
                    return None
                # 等待更多数据
                await asyncio.sleep(3)

                first_page_count = len(data_list)
                logger.info(f"第1页完成，获取到 {first_page_count} 条数据")

                # 如果需要获取指定页数据，实现翻页逻辑
                if page > 1:
                    # 清空之前的数据，只保留目标页的数据
                    data_list.clear()
                    await self._navigate_to_page(page)

                # 保持闲鱼原始顺序，便于分页；不按想要人数重排
                if page_size and len(data_list) > page_size:
                    data_list = data_list[:page_size]

                total_count = len(data_list)
                # 闲鱼搜索单页通常约 30 条；请求 page_size=50 但只返回 30 时，
                # 不能用 total_count >= page_size 误判为没有下一页
                platform_page_cap = 30
                has_more = total_count >= min(page_size or platform_page_cap, platform_page_cap)
                if total_count >= 25:
                    has_more = True

                # 尝试从捕获的 API JSON 提取真实 total
                api_total = None
                for resp in self.api_responses or []:
                    if not isinstance(resp, dict):
                        continue
                    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
                    for key in (
                        'totalCount', 'total', 'totalNum', 'resultCount',
                        'totalResults', 'numFound', 'count',
                    ):
                        val = data.get(key)
                        if val is None and isinstance(data.get('pageInfo'), dict):
                            val = data['pageInfo'].get(key)
                        if val is None and isinstance(data.get('paginator'), dict):
                            val = data['paginator'].get(key)
                        try:
                            if val is not None and int(val) > 0:
                                api_total = int(val)
                                break
                        except (TypeError, ValueError):
                            continue
                    if api_total is not None:
                        break
                    # nextPage / hasNext 也可辅助判断
                    if api_total is None:
                        next_flag = str(
                            data.get('nextPage') or data.get('hasNext') or data.get('hasMore') or ''
                        ).lower()
                        if next_flag in ('true', '1', 'yes'):
                            has_more = True

                if api_total is not None:
                    total_out = api_total
                elif has_more:
                    total_out = page * page_size + 1
                else:
                    total_out = (page - 1) * page_size + total_count

                logger.info(
                    f"搜索完成，本页 {total_count} 条真实数据，has_more={has_more}, total={total_out}"
                )

                return {
                    'items': data_list,
                    'total': total_out,
                    'has_more': has_more,
                    'page': page,
                    'page_size': page_size,
                    'is_real_data': True,
                    'source': 'playwright'
                }

            finally:
                await self.close_browser()

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Playwright 搜索失败: {error_msg}")

            # 检查是否是浏览器安装问题
            if "Executable doesn't exist" in error_msg or "playwright install" in error_msg:
                error_msg = "浏览器未安装。请在Docker容器中运行: playwright install chromium"
            elif "BrowserType.launch" in error_msg:
                error_msg = "浏览器启动失败。请确保Docker容器有足够的权限和资源"

            # 如果 Playwright 失败，返回错误信息
            return {
                'items': [],
                'total': 0,
                'error': f'搜索失败: {error_msg}'
            }

    async def _get_fallback_data(self, keyword: str, page: int, page_size: int) -> Dict[str, Any]:
        """获取备选数据（模拟数据）"""
        logger.info(f"使用备选数据: 关键词='{keyword}', 页码={page}, 每页={page_size}")

        # 模拟搜索延迟
        await asyncio.sleep(0.5)

        # 生成模拟数据
        mock_items = []
        start_index = (page - 1) * page_size

        for i in range(page_size):
            item_index = start_index + i + 1
            mock_items.append({
                'item_id': f'mock_{keyword}_{item_index}',
                'title': f'{keyword}相关商品 #{item_index} [模拟数据]',
                'price': f'{100 + item_index * 10}',
                'seller_name': f'卖家{item_index}',
                'item_url': f'https://www.goofish.com/item?id=mock_{keyword}_{item_index}',
                'publish_time': '2025-07-28',
                'tags': [f'标签{i+1}', f'分类{i+1}'],
                'main_image': f'https://via.placeholder.com/200x200?text={keyword}商品{item_index}',
                'raw_data': {
                    'mock': True,
                    'keyword': keyword,
                    'index': item_index
                }
            })

        # 模拟总数
        total_items = 100 + hash(keyword) % 500

        logger.info(f"备选数据生成完成: 找到{len(mock_items)}个商品，总计{total_items}个")

        return {
            'items': mock_items,
            'total': total_items,
            'is_fallback': True
        }

    async def _parse_real_item(self, item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析真实的闲鱼商品数据"""
        try:
            main_data = await self.safe_get(item_data, "data", "item", "main", "exContent", default={})
            click_params = await self.safe_get(item_data, "data", "item", "main", "clickParam", "args", default={})

            # 解析商品信息
            title = await self.safe_get(main_data, "title", default="未知标题")

            # 价格处理
            price_parts = await self.safe_get(main_data, "price", default=[])
            price = "价格异常"
            if isinstance(price_parts, list):
                price = "".join([str(p.get("text", "")) for p in price_parts if isinstance(p, dict)])
                price = price.replace("当前价", "").strip()

                # 统一价格格式处理
                if price and price != "价格异常":
                    # 先移除所有¥符号，避免重复
                    clean_price = price.replace('¥', '').strip()

                    # 处理万单位的价格
                    if "万" in clean_price:
                        try:
                            numeric_price = clean_price.replace('万', '').strip()
                            price_value = float(numeric_price) * 10000
                            price = f"¥{price_value:.0f}"
                        except:
                            price = f"¥{clean_price}"  # 如果转换失败，保持原样但确保有¥符号
                    else:
                        # 普通价格，确保有¥符号
                        if clean_price and (clean_price[0].isdigit() or clean_price.replace('.', '').isdigit()):
                            price = f"¥{clean_price}"
                        else:
                            price = clean_price if clean_price else "价格异常"

            # 只提取"想要人数"标签，同时尝试浏览/原价
            fish_tags_content = ""
            browse_content = ""
            ori_price = ""
            fish_tags = await self.safe_get(main_data, "fishTags", default={})

            # 遍历所有类型的标签 (r2, r3, r4等)
            for tag_type, tag_data in fish_tags.items():
                if isinstance(tag_data, dict) and "tagList" in tag_data:
                    tag_list = tag_data.get("tagList", [])
                    for tag_item in tag_list:
                        if isinstance(tag_item, dict) and "data" in tag_item:
                            content = tag_item["data"].get("content", "")
                            if content and "人想要" in content and not fish_tags_content:
                                fish_tags_content = content
                            if (
                                content
                                and not browse_content
                                and (
                                    "浏览" in content
                                    or "看过" in content
                                    or "人看过" in content
                                    or "次浏览" in content
                                    or "次看过" in content
                                )
                            ):
                                browse_content = content
                            if (
                                content
                                and not ori_price
                                and tag_item["data"].get("isStrikeThrough") in (True, "true", "1")
                            ):
                                ori_price = content

            # 其他字段解析
            area = await self.safe_get(main_data, "area", default="地区未知")
            seller = await self.safe_get(main_data, "userNickName", default="匿名卖家")
            seller_avatar = await self.safe_get(main_data, "userAvatarUrl", default="")
            if not seller_avatar:
                seller_avatar = await self.safe_get(main_data, "avatar", default="")
            raw_link = await self.safe_get(item_data, "data", "item", "main", "targetUrl", default="")
            image_url = await self.safe_get(main_data, "picUrl", default="")

            # 获取商品ID / 卖家ID
            item_id = str(await self.safe_get(click_params, "item_id", default="") or "")
            if not item_id or item_id in ("未知ID", "暂无"):
                item_id = str(await self.safe_get(click_params, "itemId", default="") or "")
            if not item_id:
                item_id = str(await self.safe_get(click_params, "id", default="") or "")
            if not item_id:
                item_id = "未知ID"
            seller_id = ""
            if isinstance(click_params, dict):
                for sk in (
                    'seller_id', 'sellerId', 'user_id', 'userId', 'uid', 'sellerIdStr',
                ):
                    if click_params.get(sk):
                        seller_id = str(click_params.get(sk))
                        break
            if not seller_id:
                seller_id = str(await self.safe_get(main_data, "userId", default="") or "")
            if not seller_id:
                seller_id = str(await self.safe_get(main_data, "sellerId", default="") or "")
            # 从跳转链接里抠 userId
            if not seller_id and raw_link:
                try:
                    import re as _re
                    m = _re.search(r'(?:userId|sellerId|uid)=(\d+)', str(raw_link))
                    if m:
                        seller_id = m.group(1)
                except Exception:
                    pass

            # 处理发布时间
            publish_time = "未知时间"
            publish_timestamp = click_params.get("publishTime", "")
            if publish_timestamp and str(publish_timestamp).isdigit():
                try:
                    publish_time = datetime.fromtimestamp(
                        int(publish_timestamp)/1000
                    ).strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            # 提取"人想要"的数字用于排序
            want_count = self._extract_want_count(fish_tags_content)
            view_count = self._extract_count_generic(browse_content) if browse_content else 0
            # 同时从 click_params 读取浏览量字段
            if not view_count and isinstance(click_params, dict):
                for vk in (
                    'browseCnt', 'browse_cnt', 'viewCnt', 'view_cnt',
                    'view_count', 'viewCount', 'pv', 'PV', 'browseCount',
                ):
                    raw_v = click_params.get(vk)
                    if raw_v is None or raw_v == '':
                        continue
                    try:
                        view_count = self._extract_count_generic(str(raw_v)) or int(float(str(raw_v)))
                    except Exception:
                        view_count = 0
                    if view_count:
                        break

            main_image = f"https:{image_url}" if image_url and not image_url.startswith("http") else image_url

            return {
                "item_id": item_id,
                "title": title,
                "price": price,
                "original_price": ori_price or "",
                "seller_name": seller,
                "seller_id": seller_id or "",
                "seller_avatar": seller_avatar if not seller_avatar or seller_avatar.startswith("http") else f"https:{seller_avatar}",
                "item_url": raw_link.replace("fleamarket://", "https://www.goofish.com/"),
                "main_image": main_image,
                "publish_time": publish_time,
                "tags": [t for t in [fish_tags_content, browse_content] if t],
                "area": area,
                "want_count": want_count,
                "want_num": want_count,
                "view_count": view_count if view_count else None,
                "browse_tag": browse_content or "",
                "want_tag": fish_tags_content or "",
                "raw_data": item_data
            }

        except Exception as e:
            logger.warning(f"解析真实商品数据失败: {str(e)}")
            return None

    def _extract_want_count(self, tags_content: str) -> int:
        """从标签内容中提取"人想要"的数字"""
        try:
            if not tags_content or "人想要" not in tags_content:
                return 0

            # 使用正则表达式提取数字
            import re
            # 匹配类似 "123人想要" 或 "1.2万人想要" 的格式
            pattern = r'(\d+(?:\.\d+)?(?:万)?)\s*人想要'
            match = re.search(pattern, tags_content)

            if match:
                number_str = match.group(1)
                if '万' in number_str:
                    # 处理万单位
                    number = float(number_str.replace('万', '')) * 10000
                    return int(number)
                else:
                    return int(float(number_str))

            return 0
        except Exception as e:
            logger.warning(f"提取想要人数失败: {str(e)}")
            return 0

    def _extract_count_generic(self, text: str) -> int:
        """从任意含数字的标签提取数量（浏览/看过等）"""
        try:
            import re
            if not text:
                return 0
            m = re.search(r'(\d+(?:\.\d+)?)\s*万?', text)
            if not m:
                return 0
            val = float(m.group(1))
            if re.search(r'\d+(?:\.\d+)?\s*万', text):
                val *= 10000
            return int(val)
        except Exception:
            return 0

    async def _navigate_to_page(self, target_page: int):
        """导航到指定页面"""
        try:
            logger.info(f"正在导航到第 {target_page} 页...")

            # 等待页面稳定
            await asyncio.sleep(2)

            # 查找并点击下一页按钮
            next_button_selectors = [
                '.search-page-tiny-arrow-right--oXVFaRao',  # 用户找到的正确选择器
                '[class*="search-page-tiny-arrow-right"]',  # 更通用的版本
                'button[aria-label="下一页"]',
                'button:has-text("下一页")',
                'a:has-text("下一页")',
                '.ant-pagination-next',
                'li.ant-pagination-next a',
                'a[aria-label="下一页"]',
                '[class*="next"]',
                '[class*="pagination-next"]',
                'button[title="下一页"]',
                'a[title="下一页"]'
            ]

            # 从第2页开始点击
            for current_page in range(2, target_page + 1):
                logger.info(f"正在点击到第 {current_page} 页...")

                next_button_found = False
                for selector in next_button_selectors:
                    try:
                        next_button = self.page.locator(selector).first

                        visible = False
                        try:
                            visible = await next_button.count() > 0 and await next_button.is_visible()
                        except Exception:
                            visible = False
                        if visible:
                            # 检查按钮是否可点击（不是禁用状态）
                            is_disabled = await next_button.get_attribute("disabled")
                            has_disabled_class = await next_button.evaluate("el => el.classList.contains('ant-pagination-disabled') || el.classList.contains('disabled')")

                            if not is_disabled and not has_disabled_class:
                                logger.info(f"找到下一页按钮，正在点击...")

                                # 滚动到按钮位置
                                await next_button.scroll_into_view_if_needed()
                                await asyncio.sleep(1)

                                # 点击下一页
                                await next_button.click()
                                await self.page.wait_for_load_state("domcontentloaded", timeout=15000)

                                # 等待新数据加载
                                await asyncio.sleep(5)

                                logger.info(f"成功导航到第 {current_page} 页")
                                next_button_found = True
                                break

                    except Exception as e:
                        continue

                if not next_button_found:
                    logger.warning(f"无法找到下一页按钮，停止在第 {current_page-1} 页")
                    break

        except Exception as e:
            logger.error(f"导航到第 {target_page} 页失败: {str(e)}")

    async def search_multiple_pages(self, keyword: str, total_pages: int = 1) -> Dict[str, Any]:
        """
        搜索多页闲鱼商品

        Args:
            keyword: 搜索关键词
            total_pages: 总页数

        Returns:
            搜索结果字典，包含所有页面的items列表和总数
        """
        browser_initialized = False
        try:
            if not PLAYWRIGHT_AVAILABLE:
                logger.error("Playwright 不可用，无法获取真实数据")
                return {
                    'items': [],
                    'total': 0,
                    'error': 'Playwright 不可用，无法获取真实数据'
                }

            logger.info(f"使用 Playwright 搜索多页闲鱼商品: 关键词='{keyword}', 总页数={total_pages}")

            # 确保浏览器初始化
            await self.init_browser()
            browser_initialized = True

            # 验证浏览器状态
            if not self.browser or not self.page:
                raise Exception("浏览器初始化失败")

            logger.info("浏览器初始化成功，开始搜索...")

            # 清空之前的API响应
            self.api_responses = []
            all_data_list = []

            # 设置API响应监听器
            async def on_response(response):
                """处理API响应，解析数据"""
                if "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search" in response.url:
                    try:
                        # 检查响应状态
                        if response.status != 200:
                            logger.warning(f"API响应状态异常: {response.status}")
                            return

                        # 安全地获取响应内容
                        try:
                            result_json = await response.json()
                        except Exception as json_error:
                            logger.warning(f"无法解析响应JSON: {str(json_error)}")
                            return

                        self.api_responses.append(result_json)
                        logger.info(f"捕获到API响应，URL: {response.url}")

                        items = result_json.get("data", {}).get("resultList", [])
                        logger.info(f"从API获取到 {len(items)} 条原始数据")

                        for item in items:
                            try:
                                parsed_item = await self._parse_real_item(item)
                                if parsed_item:
                                    all_data_list.append(parsed_item)
                            except Exception as parse_error:
                                logger.warning(f"解析单个商品失败: {str(parse_error)}")
                                continue

                    except Exception as e:
                        logger.warning(f"响应处理异常: {str(e)}")

            try:
                # 检查浏览器状态
                if not self.page or self.page.is_closed():
                    raise Exception("页面已关闭或不可用")

                # 获取并设置cookies进行登录
                logger.info("正在获取有效的cookies账户...")
                cookie_data = await self.get_first_valid_cookie()
                if not cookie_data:
                    raise Exception("未找到有效的cookies账户，请先在Cookie管理中添加有效的闲鱼账户")

                logger.info(f"使用账户: {cookie_data.get('id', 'unknown')}")

                logger.info("正在访问闲鱼首页...")
                await self.page.goto(
                    "https://www.goofish.com",
                    timeout=45000,
                    wait_until="domcontentloaded",
                )

                # 设置cookies进行登录
                logger.info("正在设置cookies进行登录...")
                cookie_success = await self.set_browser_cookies(cookie_data.get('value', ''))
                if not cookie_success:
                    logger.warning("设置cookies失败，将以未登录状态继续")
                else:
                    logger.info("✅ cookies设置成功，已登录")
                    # 刷新页面以应用cookies
                    await self.page.reload(wait_until="domcontentloaded", timeout=45000)
                    await asyncio.sleep(1.5)

                # 再次检查页面状态
                if self.page.is_closed():
                    raise Exception("页面在导航后被关闭")

                # 勿等 networkidle：闲鱼长连接/埋点会导致几乎必然超时
                logger.info("等待页面 DOM 就绪...")
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                await asyncio.sleep(1.5)

                # 再次检查页面状态
                if self.page.is_closed():
                    raise Exception("页面在等待加载后被关闭")

                # 获取页面标题和URL用于调试
                page_title = await self.page.title()
                page_url = self.page.url
                logger.info(f"当前页面标题: {page_title}")
                logger.info(f"当前页面URL: {page_url}")

                logger.info(f"正在搜索关键词: {keyword}")

                # 尝试多种搜索框选择器
                search_selectors = [
                    'input[class*="search-input"]',
                    'input[placeholder*="搜索"]',
                    'input[type="text"]',
                    '.search-input',
                    '#search-input'
                ]

                search_input = None
                for selector in search_selectors:
                    try:
                        logger.info(f"尝试查找搜索框，选择器: {selector}")
                        search_input = await self.page.wait_for_selector(selector, timeout=5000)
                        if search_input:
                            logger.info(f"✅ 找到搜索框，使用选择器: {selector}")
                            break
                    except Exception as e:
                        logger.info(f"❌ 选择器 {selector} 未找到搜索框: {str(e)}")
                        continue

                if not search_input:
                    raise Exception("未找到搜索框元素")

                # 检查页面状态
                if self.page.is_closed():
                    raise Exception("页面在查找搜索框后被关闭")

                await search_input.fill(keyword)
                logger.info(f"✅ 搜索关键词 '{keyword}' 已填入搜索框")

                # 注册响应监听
                self.page.on("response", on_response)

                logger.info("🖱️ 准备点击搜索按钮...")
                await self.page.click('button[type="submit"]')
                logger.info("✅ 搜索按钮已点击")
                    
                await self.page.wait_for_load_state("domcontentloaded", timeout=15000)

                # 等待第一页API响应（优化等待时间）
                logger.info("等待第一页API响应...")
                await asyncio.sleep(3)

                # 尝试处理弹窗
                try:
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                except:
                    pass
                # 【核心】检测并处理滑块验证 → 使用公共方法
                logger.info(f"检测是否有滑块验证...")
                slider_result = await self.handle_slider_verification(
                    page=self.page,
                    context=self.context,
                    browser=self.browser,
                    playwright=getattr(self, 'playwright', None),
                    max_retries=5
                )
                
                if not slider_result:
                    logger.error(f"❌ 滑块验证失败，搜索终止")
                    return {
                        'items': [],
                        'total': 0,
                        'error': '滑块验证失败'
                    }
                # 等待更多数据
                await asyncio.sleep(3)

                first_page_count = len(all_data_list)
                logger.info(f"第1页完成，获取到 {first_page_count} 条数据")

                # 如果需要获取更多页数据
                if total_pages > 1:
                    for page_num in range(2, total_pages + 1):
                        max_items = getattr(self, 'max_items', None)
                        if max_items and len(all_data_list) >= int(max_items):
                            logger.info(f"已达目标条数 {max_items}，停止翻页")
                            break
                        logger.info(f"正在获取第 {page_num} 页数据...")
                        await asyncio.sleep(1.5)

                        before_click_count = len(all_data_list)
                        next_button_found = False

                        # 优先 URL 直达翻页（按钮在闲鱼侧常失效/只到前几页）
                        try:
                            from urllib.parse import quote
                            enc_kw = quote(keyword)
                            for page_url in (
                                f"https://www.goofish.com/search?q={enc_kw}&page={page_num}",
                                f"https://www.goofish.com/search?q={enc_kw}&pageNumber={page_num}",
                                f"https://www.goofish.com/search?q={enc_kw}&spm=a21ybx.search.searchFilter.0&page={page_num}",
                            ):
                                logger.info(f"URL 翻页尝试: {page_url}")
                                await self.page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                                await asyncio.sleep(3.5)
                                try:
                                    await self.page.wait_for_load_state("domcontentloaded", timeout=12000)
                                except Exception:
                                    pass
                                # 滑块可能再次出现
                                try:
                                    await self.handle_slider_verification(
                                        page=self.page,
                                        context=self.context,
                                        browser=self.browser,
                                        playwright=getattr(self, 'playwright', None),
                                        max_retries=2,
                                    )
                                except Exception:
                                    pass
                                await asyncio.sleep(2)
                                if len(all_data_list) > before_click_count:
                                    logger.info(
                                        f"URL 翻页成功，第 {page_num} 页新增 {len(all_data_list) - before_click_count} 条"
                                    )
                                    next_button_found = True
                                    break
                        except Exception as url_e:
                            logger.warning(f"URL 翻页异常: {url_e}")

                        # 再尝试下一页按钮
                        if not next_button_found:
                            next_button_selectors = [
                                '.search-page-tiny-arrow-right--oXVFaRao',
                                '[class*="search-page-tiny-arrow-right"]',
                                'button[aria-label="下一页"]',
                                'button:has-text("下一页")',
                                'a:has-text("下一页")',
                                '.ant-pagination-next',
                                'li.ant-pagination-next a',
                                'a[aria-label="下一页"]',
                                '[class*="pagination"] [class*="next"]',
                            ]
                            for selector in next_button_selectors:
                                try:
                                    next_button = self.page.locator(selector).first
                                    visible = False
                                    try:
                                        visible = await next_button.count() > 0 and await next_button.is_visible()
                                    except Exception:
                                        visible = False
                                    if not visible:
                                        continue
                                    is_disabled = await next_button.get_attribute("disabled")
                                    has_disabled_class = await next_button.evaluate(
                                        "el => el.classList.contains('ant-pagination-disabled') || el.classList.contains('disabled')"
                                    )
                                    if is_disabled or has_disabled_class:
                                        continue
                                    await next_button.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.5)
                                    await next_button.click()
                                    await asyncio.sleep(4)
                                    if len(all_data_list) > before_click_count:
                                        next_button_found = True
                                        logger.info(
                                            f"按钮翻页成功，第 {page_num} 页新增 {len(all_data_list) - before_click_count} 条"
                                        )
                                        break
                                except Exception:
                                    continue

                        # 数字页码
                        if not next_button_found:
                            for num_sel in (
                                f'[class*="pagination"] >> text="{page_num}"',
                                f'li >> text="{page_num}"',
                                f'text="{page_num}"',
                            ):
                                try:
                                    loc = self.page.locator(num_sel).first
                                    if await loc.count() > 0:
                                        await loc.click(timeout=3000)
                                        await asyncio.sleep(4)
                                        if len(all_data_list) > before_click_count:
                                            next_button_found = True
                                            break
                                except Exception:
                                    continue

                        if not next_button_found:
                            # 连续两页无新增才停；单页失败可继续尝试后续页
                            logger.warning(f"第 {page_num} 页未拿到新数据，继续尝试下一页…")
                            # 若连续 2 次无增长则停止
                            fail_streak = getattr(self, '_page_fail_streak', 0) + 1
                            self._page_fail_streak = fail_streak
                            if fail_streak >= 2:
                                logger.warning(f"连续翻页无新数据，停止在第 {page_num - 1} 页")
                                break
                        else:
                            self._page_fail_streak = 0

                # 根据"人想要"数量进行倒序排列
                # 保持闲鱼原始顺序
                total_count = len(all_data_list)
                # 估算实际抓到的页数（按约 30 条/页）
                fetched_pages = max(1, (total_count + 29) // 30) if total_count else 0
                logger.info(f"多页搜索完成，总共获取到 {total_count} 条真实数据，约 {fetched_pages} 页")

                return {
                    'items': all_data_list,
                    'total': total_count,
                    'has_more': False,
                    'is_real_data': True,
                    'source': 'playwright',
                    'fetched_pages': fetched_pages,
                }

            finally:
                # 确保浏览器被正确关闭
                if browser_initialized:
                    try:
                        await self.close_browser()
                        logger.info("浏览器已安全关闭")
                    except Exception as close_error:
                        logger.warning(f"关闭浏览器时出错: {str(close_error)}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Playwright 多页搜索失败: {error_msg}")

            # 检查是否是浏览器相关问题
            if "Executable doesn't exist" in error_msg or "playwright install" in error_msg:
                error_msg = "浏览器未安装。请在Docker容器中运行: playwright install chromium"
            elif "BrowserType.launch" in error_msg:
                error_msg = "浏览器启动失败。请确保Docker容器有足够的权限和资源"
            elif "Target page, context or browser has been closed" in error_msg:
                error_msg = "浏览器页面被意外关闭。这可能是由于网站反爬虫检测或系统资源限制导致的"
            elif "Page.goto" in error_msg and "closed" in error_msg:
                error_msg = "页面导航失败，浏览器连接已断开"
            elif "Timeout" in error_msg and "exceeded" in error_msg:
                error_msg = "页面加载超时。网络连接可能不稳定或网站响应缓慢"

            # 如果 Playwright 失败，返回错误信息
            return {
                'items': [],
                'total': 0,
                'error': f'多页搜索失败: {error_msg}'
            }

    async def _get_multiple_fallback_data(self, keyword: str, total_pages: int) -> Dict[str, Any]:
        """获取多页备选数据（模拟数据）"""
        logger.info(f"使用多页备选数据: 关键词='{keyword}', 总页数={total_pages}")

        # 模拟搜索延迟
        await asyncio.sleep(1)

        # 生成多页模拟数据
        all_mock_items = []

        for page in range(1, total_pages + 1):
            page_size = 20  # 每页20条
            start_index = (page - 1) * page_size

            for i in range(page_size):
                item_index = start_index + i + 1
                all_mock_items.append({
                    'item_id': f'mock_{keyword}_{item_index}',
                    'title': f'{keyword}相关商品 #{item_index} [模拟数据-第{page}页]',
                    'price': f'{100 + item_index * 10}',
                    'seller_name': f'卖家{item_index}',
                    'item_url': f'https://www.goofish.com/item?id=mock_{keyword}_{item_index}',
                    'publish_time': '2025-07-28',
                    'tags': [f'标签{i+1}', f'分类{i+1}'],
                    'main_image': f'https://via.placeholder.com/200x200?text={keyword}商品{item_index}',
                    'raw_data': {
                        'mock': True,
                        'keyword': keyword,
                        'index': item_index,
                        'page': page
                    }
                })

        total_count = len(all_mock_items)
        logger.info(f"多页备选数据生成完成: 找到{total_count}个商品，共{total_pages}页")

        return {
            'items': all_mock_items,
            'total': total_count,
            'is_fallback': True
        }


# 搜索器工具函数

async def search_xianyu_items(
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    cookie_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    搜索闲鱼商品的便捷函数，带重试机制

    Args:
        keyword: 搜索关键词
        page: 页码
        page_size: 每页数量
        cookie_id: 指定用哪个账号 Cookie（采集页选中的账号）

    Returns:
        搜索结果
    """
    max_retries = 2
    retry_delay = 5  # 秒，增加重试间隔

    for attempt in range(max_retries + 1):
        searcher = None
        try:
            # 每次搜索都创建新的搜索器实例，避免浏览器状态混乱
            searcher = XianyuSearcher()
            if cookie_id:
                searcher.prefer_cookie_id = cookie_id

            logger.info(f"开始单页搜索，尝试次数: {attempt + 1}/{max_retries + 1}, cookie_id={cookie_id or 'auto'}")
            result = await searcher.search_items(keyword, page, page_size)

            # 如果成功获取到数据，直接返回
            if result.get('items') or not result.get('error'):
                logger.info(f"单页搜索成功，获取到 {len(result.get('items', []))} 条数据")
                return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"搜索商品失败 (尝试 {attempt + 1}/{max_retries + 1}): {error_msg}")

            # 如果是最后一次尝试，返回错误
            if attempt == max_retries:
                return {
                    'items': [],
                    'total': 0,
                    'error': f"搜索失败，已重试 {max_retries} 次: {error_msg}"
                }

            # 等待后重试
            logger.info(f"等待 {retry_delay} 秒后重试...")
            await asyncio.sleep(retry_delay)

        finally:
            # 确保搜索器被正确关闭
            if searcher:
                try:
                    await searcher.close_browser()
                except Exception as close_error:
                    logger.warning(f"关闭搜索器时出错: {str(close_error)}")

    # 理论上不会到达这里
    return {
        'items': [],
        'total': 0,
        'error': "未知错误"
    }


async def search_multiple_pages_xianyu(
    keyword: str,
    total_pages: int = 1,
    cookie_id: Optional[str] = None,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    搜索多页闲鱼商品。
    1) mtop 直连（遇风控自动过滑块，绝不污染在线 Cookie）
    2) 仍无结果时短时 Playwright 兜底（禁 networkidle，硬超时）
    """
    searcher = None
    try:
        searcher = XianyuSearcher()
        if cookie_id:
            searcher.prefer_cookie_id = cookie_id
        searcher.max_items = max_items
        logger.info(f"开始多页搜索 pages={total_pages} max_items={max_items} cookie={cookie_id}")

        api_result = await searcher.search_multiple_pages_via_api(keyword, total_pages)
        items = list(api_result.get('items') or [])
        if max_items and items:
            items = items[: int(max_items)]
            api_result['items'] = items
            api_result['total'] = len(items)

        if items:
            reached = (not max_items) or (len(items) >= int(max_items))
            if not reached:
                api_result['incomplete'] = True
                api_result['message'] = (
                    f'已采到 {len(items)} 条（目标 {max_items}），已跳过慢速浏览器补采'
                )
            logger.info(
                f"API 采集返回: {len(items)} 条 / {api_result.get('fetched_pages')} 页 "
                f"incomplete={api_result.get('incomplete')}"
            )
            return api_result

        # API 无结果：风控/令牌类不再开浏览器（只会弹过不了的滑块）
        err = api_result.get('error') or '未搜索到商品'
        err_u = str(err).upper()
        if any(k in err_u for k in ('USER_VALIDATE', 'RGV587', '重新授权', '风控', 'TOKEN', 'SESSION', '令牌')):
            logger.warning(f"API 未采到结果且为官方风控/登录态异常，跳过 Playwright: {err}")
            return {
                'items': [],
                'total': 0,
                'error': str(err),
                'source': api_result.get('source') or 'mtop-api',
                'need_reauth': True,
            }

        logger.warning(f"API 未采到结果(err={err})，尝试短时 Playwright 兜底")
        try:
            pw_result = await asyncio.wait_for(
                searcher.search_via_playwright_fast(keyword, max_items=max_items),
                timeout=40.0,
            )
            pw_items = list(pw_result.get('items') or [])
            if pw_items:
                if max_items:
                    pw_items = pw_items[: int(max_items)]
                    pw_result['items'] = pw_items
                    pw_result['total'] = len(pw_items)
                logger.info(f"Playwright 兜底采到 {len(pw_items)} 条")
                return pw_result
            if pw_result.get('error'):
                err = pw_result.get('error') or err
        except asyncio.TimeoutError:
            err = '浏览器补采超时，请稍后重试'
            logger.warning(err)
        except Exception as pe:
            logger.warning(f"Playwright 兜底失败: {pe}")
            err = str(pe) or err

        return {
            'items': [],
            'total': 0,
            'error': str(err),
            'source': api_result.get('source') or 'mtop-api',
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"多页搜索商品失败: {error_msg}")
        return {'items': [], 'total': 0, 'error': error_msg}
    finally:
        if searcher:
            try:
                await searcher.close_browser()
            except Exception as close_error:
                logger.warning(f"关闭搜索器时出错: {str(close_error)}")



