"""DFA 敏感词引擎（综合 ToolGood / Sensitive-lexicon / sensitive_content_filter 思路）。

能力：
- Trie/DFA 多模匹配 + 干扰符跳过 + 全角半角/大小写归一
- 闲鱼核心词库 + GitHub Sensitive-lexicon 扩展词库
- 联系方式/灰产短语正则
- 多轮深度重绘：替换后反复检测，直到干净或达上限
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


_SKIP_CHARS = set(
    ' \t\r\n*_-=+·•．.｡。~～`\'\"“”‘’【】[]（）()<>《》/\\|、，,；;：:！!？?@#$%^&'
)

# 开源广告词库里过宽、易误杀的词
_EXTRA_DENY = {
    '网络', '本店', '淘宝', '到货', '招聘', '兼职', '兼值', '客服', '代理', '网购',
    '全职', '有意者', '私人', '详情', '点击', '进入', '帮忙', '专业', '工作',
    'BT', 'JS', 'LY', 'SM', '小姐', 'QQ',  # QQ 以核心词库为准
    '全套', '包夜', '技师', '桑拿', '狼友', '楼凤', '胸推', '推油',  # 场景歧义大
    '3P', 'BT', '口爆', '吞精', '咪咪', '婊子', '乳方', '操逼', '性伴侣',
}

_CATEGORY_BY_EXTRA_FILE = {
    'ads.txt': ('ads', 'warn'),
    'supplement.txt': ('general', 'warn'),
    'porn_type.txt': ('illegal', 'block'),
    'violence.txt': ('illegal', 'block'),
    'guns.txt': ('illegal', 'block'),
}

_CAT_REWRITE = {
    'contact': '请通过闲鱼站内消息沟通',
    'fake': '正品成色说明',
    'finance': '正规交易说明',
    'trade': '请通过闲鱼平台担保交易',
    'grey': '合规技术说明',
    'illegal': '已删除违规表述',
    'ads': '推广说明',
    'general': '合规表述',
    'phrase': '请通过闲鱼站内消息沟通',
}

_PHRASE_REWRITE = [
    # 导流/私聊/联系方式 — 一律改成站内沟通
    (re.compile(r'可?\s*私\s*聊'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'请?\s*私\s*聊'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'私\s*信\s*我?'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'有意\s*者?\s*私'), '有意请站内留言'),
    (re.compile(r'(留|有|互换|互留)?\s*联\s*系\s*方\s*式'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'(电话|手机|短信)\s*联\s*系'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'联\s*系\s*我'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'找我\s*联\s*系'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'详\s*(谈|聊)'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'加\s*好\s*友'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'滴\s*滴?\s*我'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'来\s*私'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'私下\s*(联系|沟通|交易|聊)'), '请通过闲鱼平台担保交易'),
    (re.compile(r'(站外|线下|外部|平台外|非平台)\s*(联系|沟通|交易|聊)'), '请通过闲鱼平台担保交易'),
    (re.compile(r'引流到?\s*(微信|QQ|qq|VX|vx|V信|v信)', re.I), '请通过闲鱼站内消息沟通'),
    (re.compile(r'(加|留|滴|私)\s*(我的?)?\s*(微信|QQ|qq|VX|vx|V信|薇|扣扣)', re.I), '请通过闲鱼站内消息沟通'),
    (re.compile(r'(微信|QQ|qq|VX|vx|V信|薇信|扣扣)\s*(同号|联系|私聊)?', re.I), '请通过闲鱼站内消息沟通'),
    (re.compile(r'绕过\s*风控'), '合规流程说明'),
    (re.compile(r'风控\s*绕过'), '合规流程说明'),
    (re.compile(r'批量\s*注册\s*器?'), '注册工具说明'),
    (re.compile(r'盗号\s*脚本'), '账号安全提示'),
    (re.compile(r'破解\s*软件'), '软件功能说明'),
    (re.compile(r'远控\s*木马'), '安全风险提示'),
    (re.compile(r'不走\s*(平台|闲鱼)'), '请通过闲鱼平台担保交易'),
]

# 重绘后再清一次残留导流句式
_POST_CLEAN = [
    (re.compile(r'(可?私聊|私信|联系方式|详谈|详聊|加好友|滴我|来私)'), '请通过闲鱼站内消息沟通'),
    (re.compile(r'(微信|薇信|威信|维信|V信|v信|VX|vx|WeChat|扣扣|\bQQ\b|\bqq\b)'), '站内消息'),
]


def _to_halfwidth(s: str) -> str:
    out = []
    for ch in s:
        code = ord(ch)
        if code == 0x3000:
            out.append(' ')
        elif 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return ''.join(out)


def normalize_char(ch: str) -> str:
    ch = _to_halfwidth(ch)
    if len(ch) == 1 and ch.isascii() and ch.isalpha():
        return ch.lower()
    return ch


@dataclass
class Hit:
    word: str
    start: int
    end: int
    category: str = 'general'
    level: str = 'warn'


@dataclass
class _Node:
    children: Dict[str, '_Node'] = field(default_factory=dict)
    end: bool = False
    word: str = ''
    category: str = 'general'
    level: str = 'warn'


class DFAFilter:
    def __init__(self):
        self.root = _Node()
        self.size = 0

    def add(self, word: str, category: str = 'general', level: str = 'warn'):
        word = (word or '').strip()
        if not word or len(word) < 2:
            return
        node = self.root
        usable = 0
        for ch in word:
            key = normalize_char(ch)
            if key in _SKIP_CHARS or not key:
                continue
            usable += 1
            if key not in node.children:
                node.children[key] = _Node()
            node = node.children[key]
        if usable < 2:
            return
        if not node.end:
            self.size += 1
        node.end = True
        node.word = word
        node.category = category or 'general'
        node.level = level or 'warn'

    def find_all(self, text: str) -> List[Hit]:
        if not text:
            return []
        hits: List[Hit] = []
        n = len(text)
        i = 0
        while i < n:
            node = self.root
            j = i
            last: Optional[Tuple[int, _Node]] = None
            while j < n:
                ch = text[j]
                key = normalize_char(ch)
                if key in _SKIP_CHARS or unicodedata.category(ch).startswith('Z'):
                    j += 1
                    continue
                nxt = node.children.get(key)
                if not nxt:
                    break
                node = nxt
                j += 1
                if node.end:
                    last = (j, node)
            if last:
                end_j, end_node = last
                hits.append(
                    Hit(
                        word=end_node.word,
                        start=i,
                        end=end_j,
                        category=end_node.category,
                        level=end_node.level,
                    )
                )
                i = end_j
            else:
                i += 1
        return _merge_hits(hits)


def _merge_hits(hits: List[Hit]) -> List[Hit]:
    if not hits:
        return []
    hits = sorted(hits, key=lambda h: (h.start, -(h.end - h.start), -len(h.word)))
    merged: List[Hit] = []
    cur_end = -1
    for h in hits:
        if h.start >= cur_end:
            merged.append(h)
            cur_end = h.end
    return merged


_CONTACT_PATTERNS = [
    (re.compile(r'(?i)(v\s*x|v信|wei\s*xin|wechat|wx)\s*[:：]?\s*[a-z0-9_-]{4,}'), 'contact', 'block'),
    (re.compile(r'(?i)(qq|扣扣)\s*[:：]?\s*\d{5,12}'), 'contact', 'block'),
    (re.compile(r'(?<!\d)(1[3-9]\d{9})(?!\d)'), 'contact', 'block'),
    (re.compile(r'(?i)(加我|私我|滴我|联系我|留).{0,8}(微信|vx|v信|qq|扣扣)'), 'contact', 'block'),
    (re.compile(r'(?i)引流.{0,6}(微信|qq|vx)'), 'contact', 'block'),
    (re.compile(r'可?\s*私\s*聊'), 'contact', 'block'),
    (re.compile(r'私\s*信'), 'contact', 'block'),
    (re.compile(r'联\s*系\s*方\s*式'), 'contact', 'block'),
    (re.compile(r'详\s*(谈|聊)'), 'contact', 'block'),
    (re.compile(r'加\s*好\s*友'), 'contact', 'block'),
    (re.compile(r'私下\s*(联系|沟通|交易|聊)'), 'contact', 'block'),
    (re.compile(r'(站外|线下|外部)\s*(联系|沟通|交易)'), 'contact', 'block'),
    (re.compile(r'(?i)(木马|远控|脱壳|免杀|撞库|扫号|社工库|批量注册器?)'), 'grey', 'block'),
    (re.compile(r'(?i)(绕过|过).{0,4}(风控|验证|人机|支付)'), 'grey', 'block'),
]


class SensitiveEngine:
    def __init__(self, platform: str = 'goofish'):
        self.platform = platform
        self.dfa = DFAFilter()
        self.rewrite_map: Dict[str, str] = {}
        self.extra_loaded = 0
        self._load()

    def _base_dir(self) -> str:
        return os.path.join(os.path.dirname(__file__), 'lexicons')

    def _add_line(self, line: str, default_cat: str, default_level: str):
        line = (line or '').strip()
        if not line or line.startswith('#'):
            return
        parts = [p.strip() for p in line.split('|')]
        word = parts[0]
        if not word or word in _EXTRA_DENY:
            return
        # 纯数字过短跳过
        if word.isdigit() and len(word) < 6:
            return
        cat = parts[1] if len(parts) > 1 and parts[1] else default_cat
        level = parts[2] if len(parts) > 2 and parts[2] else default_level
        self.dfa.add(word, cat, level)

    def _load_extra_file(self, path: str, default_cat: str, default_level: str):
        if not os.path.isfile(path):
            return
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith('#'):
                    continue
                # Sensitive-lexicon 多为纯词一行；也可能「类别 词汇」
                if '|' in raw:
                    self._add_line(raw, default_cat, default_level)
                    self.extra_loaded += 1
                    continue
                parts = re.split(r'[\s\t]+', raw)
                if len(parts) >= 2 and len(parts[0]) <= 6:
                    word = parts[-1]
                else:
                    word = raw
                if word in _EXTRA_DENY or len(word) < 2:
                    continue
                before = self.dfa.size
                self.dfa.add(word, default_cat, default_level)
                if self.dfa.size > before:
                    self.extra_loaded += 1

    def _load(self):
        base = self._base_dir()
        lex_path = os.path.join(base, f'{self.platform}.txt')
        map_path = os.path.join(base, f'{self.platform}_rewrite.json')
        if os.path.isfile(lex_path):
            with open(lex_path, 'r', encoding='utf-8') as f:
                for line in f:
                    self._add_line(line, 'general', 'warn')
        # GitHub Sensitive-lexicon 扩展
        extra_dir = os.path.join(base, 'extra')
        if os.path.isdir(extra_dir):
            for fname, (cat, level) in _CATEGORY_BY_EXTRA_FILE.items():
                self._load_extra_file(os.path.join(extra_dir, fname), cat, level)
        if os.path.isfile(map_path):
            with open(map_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.rewrite_map = {str(k): str(v) for k, v in data.items()}

    def reload(self):
        self.dfa = DFAFilter()
        self.rewrite_map = {}
        self.extra_loaded = 0
        self._load()

    def detect(self, text: str) -> dict:
        text = text or ''
        hits = list(self.dfa.find_all(text))
        for pat, cat, level in _CONTACT_PATTERNS:
            for m in pat.finditer(text):
                hits.append(
                    Hit(word=m.group(0), start=m.start(), end=m.end(), category=cat, level=level)
                )
        merged = _merge_hits(hits)
        level_rank = {'info': 1, 'warn': 2, 'block': 3, 'pass': 0}
        max_level = 'pass'
        for h in merged:
            if level_rank.get(h.level, 0) > level_rank.get(max_level, 0):
                max_level = h.level
        return {
            'platform': self.platform,
            'ok': len(merged) == 0,
            'level': max_level if merged else 'pass',
            'hit_count': len(merged),
            'hits': [
                {
                    'word': h.word,
                    'start': h.start,
                    'end': h.end,
                    'category': h.category,
                    'level': h.level,
                    'snippet': text[max(0, h.start - 6) : min(len(text), h.end + 6)],
                }
                for h in merged
            ],
            'categories': sorted({h.category for h in merged}),
            'word_count': self.dfa.size,
            'extra_loaded': self.extra_loaded,
        }

    def _pick_repl(self, word: str, raw: str, category: str, mode: str) -> str:
        if mode == 'mask':
            return '*' * max(2, min(8, len(raw) or 2))
        repl = self.rewrite_map.get(word) or self.rewrite_map.get(raw)
        if repl:
            return repl
        # 模糊：词表键包含/被包含
        for k, v in self.rewrite_map.items():
            if k and (k in word or word in k or k in raw or raw in k):
                return v
        if mode == 'replace':
            return '*' * max(2, min(8, len(raw) or 2))
        return _CAT_REWRITE.get(category, '合规表述')

    def _apply_hits(self, text: str, hits: List[dict], mode: str) -> Tuple[str, List[dict]]:
        if not hits:
            return text, []
        chars = list(text)
        replacements = []
        for h in sorted(hits, key=lambda x: x['start'], reverse=True):
            raw = text[h['start'] : h['end']]
            word = h.get('word') or raw
            repl = self._pick_repl(word, raw, h.get('category') or '', mode)
            chars[h['start'] : h['end']] = list(repl)
            replacements.append(
                {'from': raw, 'to': repl, 'word': word, 'category': h.get('category')}
            )
        return ''.join(chars), list(reversed(replacements))

    def _phrase_rewrite(self, text: str) -> Tuple[str, List[dict]]:
        reps = []
        out = text
        for pat, repl in _PHRASE_REWRITE:
            def _sub(m, _repl=repl):
                reps.append({'from': m.group(0), 'to': _repl, 'word': m.group(0), 'category': 'phrase'})
                return _repl

            out, n = pat.subn(_sub, out)
            if n:
                pass
        return out, reps

    def _post_clean(self, text: str) -> Tuple[str, List[dict]]:
        """重绘后清残留：私聊/联系方式/微信等不允许再出现。"""
        reps = []
        out = text
        for pat, repl in _POST_CLEAN:
            def _sub(m, _repl=repl):
                reps.append({'from': m.group(0), 'to': _repl, 'word': m.group(0), 'category': 'post_clean'})
                return _repl

            out, n = pat.subn(_sub, out)
            if n:
                pass
        # 合并重复的站内沟通提示
        out2 = re.sub(
            r'(请通过闲鱼站内消息沟通)(?:[，,、\s]*请通过闲鱼站内消息沟通)+',
            r'\1',
            out,
        )
        if out2 != out:
            reps.append({'from': '(重复提示)', 'to': '请通过闲鱼站内消息沟通', 'word': 'dedupe', 'category': 'post_clean'})
            out = out2
        return out, reps

    def rewrite(self, text: str, mode: str = 'smart', deep: bool = True, max_rounds: int = 8) -> dict:
        """mode: mask | replace | smart；deep=True 时多轮直到无命中或达上限。"""
        text = text or ''
        original = text
        all_reps: List[dict] = []
        rounds = 0
        current = text

        current, phrase_reps = self._phrase_rewrite(current)
        all_reps.extend(phrase_reps)

        limit = max_rounds if deep else 1
        last_det = self.detect(current)
        for _ in range(limit):
            rounds += 1
            det = self.detect(current)
            last_det = det
            if not det.get('hits'):
                break
            current, reps = self._apply_hits(current, det['hits'], mode)
            all_reps.extend(reps)
            current, phrase_reps = self._phrase_rewrite(current)
            all_reps.extend(phrase_reps)
            current, post_reps = self._post_clean(current)
            all_reps.extend(post_reps)
            if not reps and not phrase_reps and not post_reps:
                break

        # 最终再清一次 + 复检
        current, post_reps = self._post_clean(current)
        all_reps.extend(post_reps)
        final_det = self.detect(current)
        # 若仍有导流类命中，强制再替换一轮
        if final_det.get('hits') and deep:
            current, reps = self._apply_hits(current, final_det['hits'], mode)
            all_reps.extend(reps)
            current, _ = self._post_clean(current)
            final_det = self.detect(current)

        return {
            'platform': self.platform,
            'mode': mode,
            'deep': deep,
            'rounds': rounds,
            'original': original,
            'rewritten': current,
            'changed': current != original,
            'clean': bool(final_det.get('ok')),
            'remaining_hits': final_det.get('hit_count') or 0,
            'replacements': all_reps,
            'detect': last_det,
            'final_detect': final_det,
            'word_count': self.dfa.size,
            'extra_loaded': self.extra_loaded,
        }


_ENGINES: Dict[str, SensitiveEngine] = {}


def get_engine(platform: str = 'goofish') -> SensitiveEngine:
    platform = (platform or 'goofish').strip().lower()
    key = 'goofish' if platform in ('goofish', 'xianyu') else platform
    eng = _ENGINES.get(key)
    if eng is None:
        eng = SensitiveEngine('goofish' if key == 'goofish' else key)
        _ENGINES[key] = eng
    return eng


def list_platforms() -> List[dict]:
    return [
        {'id': 'goofish', 'name': '闲鱼', 'ready': True},
        {'id': 'taobao', 'name': '淘宝', 'ready': False},
        {'id': 'pinduoduo', 'name': '拼多多', 'ready': False},
        {'id': 'douyin', 'name': '抖音电商', 'ready': False},
    ]
