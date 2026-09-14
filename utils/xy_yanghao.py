"""养号任务：轻量协议浏览 + 留言（绝不卡死）+ 实时商品明细。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class YanghaoJob:
    cookie_id: str
    keyword: str
    target_count: int = 50
    dwell_sec: float = 10.0
    leave_msg: bool = True
    message_text: str = '非常好，效果不错～'
    loop_times: int = 1
    status: str = 'idle'  # idle|running|paused|stopped|done
    browsed: int = 0
    messaged: int = 0
    msg_failed: int = 0
    browse_failed: int = 0
    today_count: int = 0
    logs: List[str] = field(default_factory=list)
    records: List[Dict[str, Any]] = field(default_factory=list)
    _pause_event: Optional[asyncio.Event] = field(default=None, repr=False)
    _stop: bool = False
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    def __post_init__(self):
        if self._pause_event is None:
            self._pause_event = asyncio.Event()
        self._pause_event.set()

    def log(self, msg: str):
        line = f'{time.strftime("%H:%M:%S")} {msg}'
        self.logs.append(line)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
        logger.info(f'[养号][{self.cookie_id}] {msg}')


_JOBS: Dict[str, YanghaoJob] = {}
_TODAY: Dict[str, Dict[str, int]] = {}


def _today_key() -> str:
    return time.strftime('%Y-%m-%d')


def get_today_stats(cookie_id: str) -> dict:
    d = _TODAY.get(cookie_id) or {}
    return {'date': _today_key(), 'count': int(d.get(_today_key(), 0))}


def bump_today(cookie_id: str, n: int = 1):
    day = _today_key()
    bucket = _TODAY.setdefault(cookie_id, {})
    bucket[day] = int(bucket.get(day, 0)) + n


def get_job(cookie_id: str) -> Optional[YanghaoJob]:
    return _JOBS.get(cookie_id)


def job_snapshot(job: YanghaoJob) -> dict:
    return {
        'cookie_id': job.cookie_id,
        'keyword': job.keyword,
        'target_count': job.target_count,
        'dwell_sec': job.dwell_sec,
        'leave_msg': job.leave_msg,
        'message_text': job.message_text,
        'loop_times': job.loop_times,
        'status': job.status,
        'browsed': job.browsed,
        'messaged': job.messaged,
        'msg_failed': job.msg_failed,
        'browse_failed': job.browse_failed,
        'logs': list(job.logs[-150:]),
        'records': list(job.records[-500:]),
        'today': get_today_stats(job.cookie_id),
        'progress': f'{job.browsed}/{job.target_count}',
        'engine': 'yanghao-v3-nohang',
    }


def _pick_str(d: dict, *keys) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ''


def _normalize_item(item: dict) -> dict:
    item = item or {}
    item_id = _pick_str(item, 'item_id', 'id', 'itemId')
    pic = _pick_str(
        item,
        'pic_url', 'item_pic', 'main_image', 'pictUrl', 'picUrl', 'image', 'cover',
    )
    if not pic:
        pi = item.get('pic_info') or item.get('picInfo') or {}
        if isinstance(pi, dict):
            pic = _pick_str(pi, 'picUrl', 'url', 'img')
    seller_id = _pick_str(
        item,
        'seller_id', 'sellerId', 'seller_user_id', 'user_id', 'userId', 'uid', 'sellerIdStr',
    )
    # 嵌套用户信息（搜索卡片常见）
    if not seller_id:
        for nest_k in ('user', 'userInfo', 'seller', 'sellerInfo', 'owner', 'detailParams', 'clickParam', 'trackParams'):
            nest = item.get(nest_k)
            if not isinstance(nest, dict):
                continue
            seller_id = _pick_str(
                nest,
                'seller_id', 'sellerId', 'user_id', 'userId', 'uid', 'sellerIdStr', 'id',
            )
            if seller_id:
                break
    if not seller_id:
        link = _pick_str(item, 'item_url', 'web_url', 'detailUrl', 'detail_url', 'targetUrl')
        if link:
            import re as _re
            m = _re.search(r'(?:userId|sellerId|uid)=(\d+)', link)
            if m:
                seller_id = m.group(1)
    return {
        'item_id': item_id,
        'title': _pick_str(item, 'title', 'item_title') or item_id,
        'price': _pick_str(item, 'price', 'item_price', 'soldPrice') or '-',
        'original_price': _pick_str(item, 'original_price', 'oriPrice', 'originPrice') or '-',
        'pic_url': pic,
        'seller_id': seller_id,
        'seller_nick': _pick_str(item, 'seller_nick', 'sellerNick', 'user_nick', 'nick', 'seller_name') or '-',
        'want_num': item.get('want_num') or item.get('want_count') or item.get('wantCnt') or 0,
        'view_count': item.get('view_count') or item.get('viewCount') or item.get('browseCnt') or 0,
        'area': _pick_str(item, 'area', 'city', 'location') or '',
        'web_url': item.get('item_url') or item.get('web_url') or (
            f'https://www.goofish.com/item?id={item_id}' if item_id else ''
        ),
    }


async def _wait_pause(job: YanghaoJob):
    while job._pause_event and not job._pause_event.is_set():
        job.status = 'paused'
        await asyncio.sleep(0.25)
    if not job._stop:
        job.status = 'running'


async def _dwell(job: YanghaoJob, item_id: str):
    """停留期间可热更新 dwell_sec（暂停改设置后继续立即生效）。"""
    waited = 0.0
    while True:
        if job._stop:
            return
        await _wait_pause(job)
        if job._stop:
            return
        dwell = max(1.0, float(job.dwell_sec or 10))
        if waited >= dwell:
            break
        if waited == 0:
            job.log(f'停留 {dwell:.0f}s 后继续…（{item_id}）')
        step = min(0.5, dwell - waited)
        await asyncio.sleep(step)
        waited += step
    job.log(f'停留结束，处理下一项（{item_id}）')


async def _browse_one(item: dict, job: YanghaoJob, round_no: int) -> dict:
    """仅用搜索结果记浏览，绝不调用 get_item_info（会滑块卡死）。"""
    row = _normalize_item(item)
    item_id = row['item_id']
    rec = {
        **row,
        'browse_status': 'pending',
        'msg_status': 'skip' if not job.leave_msg else 'pending',
        'msg_detail': '',
        'round': round_no,
        'ts': time.strftime('%H:%M:%S'),
    }
    # 先入表，前端立刻能看到
    job.records.append(rec)

    if not item_id:
        rec['browse_status'] = 'fail'
        rec['msg_status'] = 'skip'
        rec['msg_detail'] = '无商品ID'
        job.browse_failed += 1
        job.log('跳过：商品无 ID')
        return rec

    # 列表曝光即计浏览（养号核心：停留节奏，不打详情）
    await asyncio.sleep(0.15)
    rec['browse_status'] = 'ok'
    job.browsed += 1
    bump_today(job.cookie_id, 1)
    job.log(
        f'[{job.browsed}/{job.target_count}] 已浏览 {item_id} 「{(row["title"] or "")[:24]}」'
        f' 卖家={row.get("seller_id") or "-"}'
    )
    return rec


async def _send_leave_msg_safe(cookie_id: str, seller_id: str, item_id: str, text: str) -> str:
    """优先在线 WS 建会话发私信；失败则独立 WS 通道重试（send_msg_once）。"""
    from XianyuAutoAsync import XianyuLive

    seller_id = str(seller_id or '').strip().split('@')[0]
    item_id = str(item_id or '').strip()
    text = str(text or '').strip()
    if not seller_id:
        raise RuntimeError('卖家ID为空')
    if not text:
        raise RuntimeError('留言内容为空')

    online = XianyuLive.get_instance(cookie_id)
    last_err = None

    if online and getattr(online, 'ws', None) and not online.ws.closed:
        for attempt in range(3):
            try:
                # 偶发「闲鱼走神了」：退避重试；第 2 次起不带 itemId 再建一次
                use_item = item_id if attempt == 0 else ''
                info = await asyncio.wait_for(
                    online.ensure_chat_conversation(seller_id, item_id=use_item),
                    timeout=15.0,
                )
                cid = str((info or {}).get('chat_id') or '').split('@')[0]
                if not cid:
                    raise RuntimeError('创建会话失败（平台未返回 chat_id）')
                await asyncio.wait_for(online.send_msg(online.ws, cid, seller_id, text), timeout=10.0)
                return f'ok:online-ws(try={attempt + 1})'
            except Exception as e:
                last_err = e
                await asyncio.sleep(1.2 + attempt * 1.5)

    # 独立短连接兜底（不依赖主通道 create 回包解析）
    try:
        live = online
        if not live:
            raise RuntimeError('账号未在线，无法留言（请先保持消息通道在线）')
        await asyncio.wait_for(live.send_msg_once(seller_id, item_id or '0', text), timeout=25.0)
        return 'ok:send-once'
    except Exception as e:
        if last_err:
            raise RuntimeError(f'{last_err}；兜底也失败: {e}') from e
        raise


async def _leave_message(rec: dict, job: YanghaoJob) -> bool:
    if not job.leave_msg:
        rec['msg_status'] = 'skip'
        rec['msg_detail'] = '未开启自动留言'
        return False

    text = (job.message_text or '').strip()
    item_id = str(rec.get('item_id') or '')
    seller_id = str(rec.get('seller_id') or '').split('@')[0]
    job.log(f'准备留言 {item_id} → 卖家 {seller_id or "无"}')

    if not text:
        rec['msg_status'] = 'fail'
        rec['msg_detail'] = '留言内容为空'
        job.msg_failed += 1
        job.log(f'留言失败 {item_id}：内容为空')
        return False
    if not item_id or not seller_id:
        rec['msg_status'] = 'fail'
        rec['msg_detail'] = '缺卖家ID（搜索结果未带回，跳过）'
        job.msg_failed += 1
        job.log(f'留言失败 {item_id}：缺卖家ID')
        return False

    try:
        how = await _send_leave_msg_safe(job.cookie_id, seller_id, item_id, text)
        rec['msg_status'] = 'ok'
        rec['msg_detail'] = f'留言成功（{how}）'
        job.messaged += 1
        job.log(f'留言成功 {item_id} → {seller_id}')
        # 降低「闲鱼走神了」风控：留言间隔
        await asyncio.sleep(2.5)
        return True
    except asyncio.TimeoutError:
        rec['msg_status'] = 'fail'
        rec['msg_detail'] = '留言超时'
        job.msg_failed += 1
        job.log(f'留言超时 {item_id}')
        return False
    except Exception as e:
        err = str(e)
        if '走神' in err or 'EXCEPTION' in err:
            err = f'平台限流/风控（闲鱼走神了），已重试仍失败：{err[:180]}'
        rec['msg_status'] = 'fail'
        rec['msg_detail'] = f'留言失败：{err}'
        job.msg_failed += 1
        job.log(f'留言失败 {item_id}: {err}')
        await asyncio.sleep(3.0)
        return False


async def _run_job(job: YanghaoJob, live_factory):
    job.status = 'running'
    job._stop = False
    if job._pause_event is None:
        job._pause_event = asyncio.Event()
        job._pause_event.set()
    job.log(
        f'开始养号：关键词「{job.keyword}」目标 {job.target_count} 件，'
        f'停留 {job.dwell_sec}s，循环 {job.loop_times} 轮，留言={"开" if job.leave_msg else "关"}'
        f'（引擎 yanghao-v3-nohang）'
    )
    live = None
    created = False
    try:
        # live 仅作 cookie 上下文备用；养号主流程不再打详情
        try:
            live, created = live_factory()
        except Exception as e:
            job.log(f'临时会话创建警告（可忽略）: {e}')
            live, created = None, False

        for round_i in range(max(1, int(job.loop_times or 1))):
            if job._stop:
                break
            round_no = round_i + 1
            job.log(f'—— 第 {round_no}/{job.loop_times} 轮 ——')

            items: List[dict] = []
            try:
                from utils.item_search import search_multiple_pages_xianyu

                want = max(1, min(int(job.target_count or 50), 500))
                pages = max(1, min(40, (want + 29) // 30))
                job.log(f'正在搜索「{job.keyword}」约 {want} 条（{pages} 页）…')
                res = await search_multiple_pages_xianyu(
                    keyword=job.keyword,
                    total_pages=pages,
                    cookie_id=job.cookie_id,
                    max_items=want,
                )
                if isinstance(res, dict):
                    items = list(res.get('items') or res.get('data') or [])
                    if res.get('error') and not items:
                        job.log(f'搜索失败：{res.get("error")}')
                    elif res.get('error'):
                        job.log(f'搜索警告：{res.get("error")}')
                    elif res.get('message'):
                        job.log(str(res.get('message')))
                    job.log(f'搜索完成：拿到 {len(items)} 条（来源 {res.get("source") or "-"}）')
                elif isinstance(res, list):
                    items = res
                    job.log(f'搜索完成：拿到 {len(items)} 条')
            except Exception as e:
                job.log(f'搜索失败: {e}')
                items = []

            if not items:
                job.log('未搜到商品，结束本轮')
                continue

            items = items[: int(job.target_count or 50)]
            job.log(f'本轮待处理 {len(items)} 件（目标 {job.target_count}）')

            for idx, item in enumerate(items):
                if job._stop:
                    break
                await _wait_pause(job)
                if job._stop:
                    break

                job.log(f'--- 第 {idx + 1}/{len(items)} 件 ---')
                rec = await _browse_one(item, job, round_no)
                await _dwell(job, str(rec.get('item_id') or ''))
                if job._stop:
                    break
                await _leave_message(rec, job)
                await asyncio.sleep(0.35)

        job.status = 'stopped' if job._stop else 'done'
        job.log(
            f'养号结束：浏览 {job.browsed}，浏览失败 {job.browse_failed}，'
            f'留言成功 {job.messaged}，留言失败 {job.msg_failed}；'
            f'今日累计 {get_today_stats(job.cookie_id)["count"]}'
        )
    except Exception as e:
        job.status = 'stopped'
        job.log(f'任务异常中断: {e}')
        logger.exception(f'[养号][{job.cookie_id}] 任务异常')
    finally:
        if created and live and hasattr(live, 'close_session'):
            try:
                await live.close_session()
            except Exception:
                pass


def start_job(cookie_id: str, cfg: dict, live_factory) -> YanghaoJob:
    old = _JOBS.get(cookie_id)
    if old and old._task and not old._task.done() and old.status in ('running', 'paused'):
        raise RuntimeError('该账号已有养号任务在运行，请先暂停/停止')
    if old and old._task and not old._task.done():
        old._stop = True
        if old._pause_event:
            old._pause_event.set()

    keyword = str(cfg.get('keyword') or '').strip()
    if not keyword:
        raise RuntimeError('请填写搜索关键词')

    job = YanghaoJob(
        cookie_id=cookie_id,
        keyword=keyword,
        target_count=max(1, min(500, int(cfg.get('target_count') or 50))),
        dwell_sec=max(1.0, min(120.0, float(cfg.get('dwell_sec') or 10))),
        leave_msg=bool(cfg.get('leave_msg', True)),
        message_text=str(cfg.get('message_text') or '非常好，效果不错～'),
        loop_times=max(1, min(20, int(cfg.get('loop_times') or 1))),
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as e:
        raise RuntimeError(f'无法启动养号任务（无事件循环）: {e}') from e
    job._task = loop.create_task(_run_job(job, live_factory))
    _JOBS[cookie_id] = job
    return job


def pause_job(cookie_id: str) -> YanghaoJob:
    job = _JOBS.get(cookie_id)
    if not job:
        raise RuntimeError('没有养号任务')
    if job._pause_event is None:
        job._pause_event = asyncio.Event()
    job._pause_event.clear()
    job.status = 'paused'
    job.log('已暂停')
    return job


def resume_job(cookie_id: str, cfg: Optional[dict] = None) -> YanghaoJob:
    job = _JOBS.get(cookie_id)
    if not job:
        raise RuntimeError('没有养号任务')
    changes = apply_job_settings(job, cfg)
    if changes:
        job.log('检测到设置已修改，按最新配置继续：' + '；'.join(changes))
    else:
        job.log('已继续（配置未变更）')
    if job._pause_event is None:
        job._pause_event = asyncio.Event()
    job._pause_event.set()
    job.status = 'running'
    return job


def apply_job_settings(job: YanghaoJob, cfg: Optional[dict]) -> list:
    """暂停/继续时把前端最新表单写回任务，返回变更说明。"""
    if not cfg or not isinstance(cfg, dict):
        return []
    changes = []
    if 'keyword' in cfg:
        kw = str(cfg.get('keyword') or '').strip()
        if kw and kw != job.keyword:
            changes.append(f'关键词 {job.keyword}→{kw}')
            job.keyword = kw
    if 'target_count' in cfg:
        try:
            n = max(1, min(500, int(cfg.get('target_count') or job.target_count)))
            if n != job.target_count:
                changes.append(f'浏览数量 {job.target_count}→{n}')
                job.target_count = n
        except Exception:
            pass
    if 'dwell_sec' in cfg:
        try:
            d = max(1.0, min(120.0, float(cfg.get('dwell_sec') or job.dwell_sec)))
            if abs(d - float(job.dwell_sec or 0)) > 0.01:
                changes.append(f'停留 {job.dwell_sec}s→{d}s')
                job.dwell_sec = d
        except Exception:
            pass
    if 'loop_times' in cfg:
        try:
            n = max(1, min(20, int(cfg.get('loop_times') or job.loop_times)))
            if n != job.loop_times:
                changes.append(f'循环 {job.loop_times}→{n}')
                job.loop_times = n
        except Exception:
            pass
    if 'leave_msg' in cfg:
        lm = bool(cfg.get('leave_msg'))
        if lm != bool(job.leave_msg):
            changes.append(f'留言 {"开" if lm else "关"}')
            job.leave_msg = lm
    if 'message_text' in cfg:
        text = str(cfg.get('message_text') or '')
        if text != job.message_text:
            changes.append('留言文案已更新')
            job.message_text = text
    return changes


def stop_job(cookie_id: str) -> YanghaoJob:
    job = _JOBS.get(cookie_id)
    if not job:
        raise RuntimeError('没有养号任务')
    job._stop = True
    if job._pause_event is None:
        job._pause_event = asyncio.Event()
    job._pause_event.set()
    job.status = 'stopped'
    job.log('已请求停止')
    return job
