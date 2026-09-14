"""从闲鱼商品卡片标签中提取想要/浏览/曝光/原价等字段。"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


def _iter_tag_contents(label_data: Any):
    if not isinstance(label_data, dict):
        return
    # itemLabelDataVO: { labelData: { r2: {tagList: [...]}, r3: {...} } }
    buckets = label_data.get('labelData') if 'labelData' in label_data else label_data
    if not isinstance(buckets, dict):
        return
    for _k, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for tag in bucket.get('tagList') or []:
            if not isinstance(tag, dict):
                continue
            data = tag.get('data') or tag
            if isinstance(data, dict):
                content = str(data.get('content') or '')
                if content:
                    yield content, data


def parse_count_text(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*万?', text)
    if not m:
        return None
    val = float(m.group(1))
    if '万' in text[m.start() : m.end() + 1] or '万' in text:
        # 更稳妥：匹配数字后紧跟万
        if re.search(r'\d+(?:\.\d+)?\s*万', text):
            val *= 10000
    return int(val)


def _pick_int(src: dict, keys: tuple) -> Optional[int]:
    for k in keys:
        if src.get(k) not in (None, '', '-'):
            try:
                return int(float(str(src.get(k)).replace(',', '')))
            except Exception:
                pass
    return None


def extract_item_metrics(card_or_detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    从商品卡片 / item_detail JSON 提取：
    want_num, view_count(浏览), exposure_count(曝光), original_price, price
    """
    if not isinstance(card_or_detail, dict):
        return {}

    # 兼容嵌套 item / detail / data
    sources = [card_or_detail]
    for nest_key in ('item', 'detail', 'data', 'itemDO', 'itemInfo', 'sellerItem', 'itemDetail'):
        nested = card_or_detail.get(nest_key)
        if isinstance(nested, dict):
            sources.append(nested)

    want_num = None
    view_count = None
    exposure_count = None
    original_price = None

    want_keys = ('wantNum', 'want_num', 'wantCnt', 'want_count', 'collectNum', 'collect_count')
    view_keys = (
        'browseCnt', 'browse_count', 'browseCount', 'viewCnt', 'view_count', 'viewCount',
        'pv', 'browse', 'pageView', 'page_view',
    )
    exposure_keys = (
        'exposureCnt', 'exposure_count', 'exposureCount', 'exposeCnt', 'expose_count',
        'exposeCount', 'impressionCnt', 'impression', 'exposure', 'showCnt', 'show_count',
    )

    for src in sources:
        if want_num is None:
            want_num = _pick_int(src, want_keys)
        if view_count is None:
            view_count = _pick_int(src, view_keys)
        if exposure_count is None:
            exposure_count = _pick_int(src, exposure_keys)
        if original_price is None:
            for k in (
                'originalPrice',
                'oriPrice',
                'originPrice',
                'original_price',
                'struckPrice',
                'origPrice',
                'priceOrigin',
            ):
                v = src.get(k)
                if v not in (None, '', '-'):
                    original_price = str(v)
                    break
            # itemPriceDTO / priceDTO 里的分单位原价
            for nest_k in ('itemPriceDTO', 'priceDTO', 'item_price_dto'):
                nest = src.get(nest_k)
                if isinstance(nest, dict) and original_price is None:
                    for pk in ('origPriceInCent', 'oriPriceInCent', 'originalPriceInCent', 'oriPrice', 'originalPrice'):
                        pv = nest.get(pk)
                        if pv in (None, '', '-'):
                            continue
                        try:
                            if 'Cent' in pk or (isinstance(pv, (int, float)) and float(pv) > 1000):
                                original_price = str(round(float(pv) / 100.0, 2))
                            else:
                                original_price = str(pv)
                            break
                        except Exception:
                            original_price = str(pv)
                            break
            # 价格文案里「原价¥xx」
            if original_price is None:
                for tk in ('price_text', 'priceText', 'priceDesc'):
                    text = str(src.get(tk) or '')
                    m = re.search(r'原价\s*[¥￥]?\s*(\d+(?:\.\d+)?)', text)
                    if m:
                        original_price = m.group(1)
                        break
        # trackParams / detailParams 里偶发带计数
        for nest in ('trackParams', 'detailParams', 'detail_params', 'ext', 'extra'):
            nested = src.get(nest)
            if isinstance(nested, dict):
                if want_num is None:
                    want_num = _pick_int(nested, want_keys)
                if view_count is None:
                    view_count = _pick_int(nested, view_keys)
                if exposure_count is None:
                    exposure_count = _pick_int(nested, exposure_keys)

    # 嵌套 label
    label_sources = []
    for src in sources:
        label_sources.extend(
            [
                src.get('item_label_data'),
                src.get('itemLabelDataVO'),
                src.get('itemLabelData'),
                src.get('itemLabelExtList'),
                (src.get('detail_params') or {}).get('itemLabelDataVO')
                if isinstance(src.get('detail_params'), dict)
                else None,
            ]
        )
    for src in label_sources:
        if not src:
            continue
        # itemLabelExtList 可能是 list
        if isinstance(src, list):
            for tag in src:
                if not isinstance(tag, dict):
                    continue
                content = str(tag.get('text') or tag.get('content') or tag.get('valueName') or '')
                if '想要' in content and want_num is None:
                    want_num = parse_count_text(content)
                if ('浏览' in content or '人看过' in content or '次浏览' in content) and view_count is None:
                    view_count = parse_count_text(content)
                if '曝光' in content and exposure_count is None:
                    exposure_count = parse_count_text(content)
            continue
        for content, data in _iter_tag_contents(src):
            if '想要' in content and want_num is None:
                want_num = parse_count_text(content)
            if ('浏览' in content or '人看过' in content or '次浏览' in content) and view_count is None:
                view_count = parse_count_text(content)
            if '曝光' in content and exposure_count is None:
                exposure_count = parse_count_text(content)
            if (
                original_price is None
                and (
                    data.get('isStrikeThrough') in (True, 'true', '1')
                    or '原价' in content
                )
                and ('¥' in content or '￥' in content or re.search(r'\d', content))
            ):
                original_price = content.replace('原价', '').strip()

    # fishTags（搜索结果）
    for src in sources:
        fish_tags = src.get('fishTags') or src.get('tags')
        if isinstance(fish_tags, dict):
            for content, data in _iter_tag_contents(fish_tags):
                if '想要' in content and want_num is None:
                    want_num = parse_count_text(content)
                if ('浏览' in content or '看过' in content) and view_count is None:
                    view_count = parse_count_text(content)
                if '曝光' in content and exposure_count is None:
                    exposure_count = parse_count_text(content)
        elif isinstance(fish_tags, list):
            for t in fish_tags:
                content = t if isinstance(t, str) else str((t or {}).get('content') or t or '')
                if '想要' in content and want_num is None:
                    want_num = parse_count_text(content)
                if ('浏览' in content or '看过' in content) and view_count is None:
                    view_count = parse_count_text(content)
                if '曝光' in content and exposure_count is None:
                    exposure_count = parse_count_text(content)

    # 卖家中心列表常只有「浏览/想要」，真正曝光多在卖家数据中心；有浏览无曝光时用浏览作展示兜底并打标记
    exposure_approx = False
    if exposure_count is None and view_count is not None:
        exposure_count = view_count
        exposure_approx = True

    pic = ''
    pic_info = card_or_detail.get('pic_info') or card_or_detail.get('picInfo') or {}
    detail_params = card_or_detail.get('detail_params') or card_or_detail.get('detailParams') or {}
    if isinstance(pic_info, dict):
        pic = pic_info.get('picUrl') or pic_info.get('url') or ''
    if not pic and isinstance(detail_params, dict):
        pic = detail_params.get('picUrl') or ''
    if not pic:
        pic = (
            card_or_detail.get('picUrl')
            or card_or_detail.get('main_image')
            or card_or_detail.get('item_pic')
            or ''
        )

    return {
        'want_num': want_num,
        'view_count': view_count,
        'exposure_count': exposure_count,
        'exposure_approx': exposure_approx,
        'original_price': original_price or '',
        'item_pic': pic,
    }


def normalize_pic_url(url: Any) -> str:
    if not url:
        return ''
    s = str(url).strip()
    if not s:
        return ''
    if s.startswith('//'):
        return 'https:' + s
    if s.startswith('http://') or s.startswith('https://'):
        return s
    if s.startswith('img.alicdn.com') or s.startswith('gw.alicdn.com') or '.' in s.split('/')[0]:
        return 'https://' + s.lstrip('/')
    return s


def pick_thumb_from_parsed(parsed: Dict[str, Any]) -> str:
    m = extract_item_metrics(parsed if isinstance(parsed, dict) else {})
    if m.get('item_pic'):
        return normalize_pic_url(m['item_pic'])
    if not isinstance(parsed, dict):
        return ''
    nested = parsed.get('pic_info') or parsed.get('picInfo') or {}
    if isinstance(nested, dict) and nested.get('picUrl'):
        return normalize_pic_url(nested['picUrl'])
    dp = parsed.get('detail_params') or {}
    if isinstance(dp, dict) and dp.get('picUrl'):
        return normalize_pic_url(dp['picUrl'])
    for k in ('picUrl', 'pic_url', 'mainPic', 'main_image', 'image', 'pictUrl'):
        v = parsed.get(k)
        if isinstance(v, str) and v:
            return normalize_pic_url(v)
    imgs = parsed.get('imageInfos') or parsed.get('images') or []
    if isinstance(imgs, list) and imgs:
        first = imgs[0]
        if isinstance(first, dict):
            return normalize_pic_url(first.get('url') or first.get('picUrl') or '')
        if isinstance(first, str):
            return normalize_pic_url(first)
    return ''
