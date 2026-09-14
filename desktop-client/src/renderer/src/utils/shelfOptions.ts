/** 高质量本地去重：标题/描述改写（前端即时预览；后端发布再处理一次） */

export const TITLE_MAX_LEN = 30

export function truncateTitle(title: string, max = TITLE_MAX_LEN): string {
  const t = String(title || '').trim()
  return t.length > max ? t.slice(0, max) : t
}

const WORD_PAIRS: Array<[string, string]> = [
  ['安装包', '安装文件'],
  ['完整版', '全功能版'],
  ['旗舰版', '专业版'],
  ['最新版', '新版本'],
  ['永久', '长期'],
  ['激活码', '授权码'],
  ['序列号', '注册码'],
  ['教程', '学习资料'],
  ['全集', '整套资料'],
  ['打包', '合集'],
  ['软件', '应用工具'],
  ['插件', '扩展组件'],
  ['下载即用', '拿到就能用'],
  ['开箱即用', '即装即用'],
  ['包更新', '支持更新'],
  ['免费更新', '可持续更新'],
  ['正版', '正规渠道'],
  ['破解', '绿色可用'],
  ['虚拟', '数字化'],
  ['发货', '交付'],
  ['秒发', '及时交付'],
  ['自动发货', '付款后自动交付'],
  ['售后', '使用指导'],
  ['包教会', '可远程指导'],
  ['远程', '在线协助'],
  ['便宜', '高性价比'],
  ['优惠', '特惠'],
  ['促销', '限时福利'],
  ['急出', '诚心出'],
  ['闲置', '个人转让'],
  ['几乎全新', '成色很好'],
  ['九成新', '使用痕迹很少'],
  ['原装', '原厂配套'],
  ['正品', '品质可靠'],
  ['支持验货', '可先验再确认'],
  ['包邮', '含运'],
  ['勿刀', '价格可小议'],
  ['可小刀', '可小幅议价'],
  ['同城面交', '同城可约'],
  ['资料齐全', '文档齐全'],
  ['含教程', '附学习说明'],
  ['一键安装', '简易安装'],
  ['绿色版', '免安装版'],
  ['便携版', '免装版'],
  ['win10', 'Windows10'],
  ['win11', 'Windows11'],
  ['CAD', '绘图设计'],
  ['PS', '图像处理'],
  ['AE', '视频特效'],
  ['PR', '剪辑软件'],
  ['Office', '办公套件'],
  ['WPS', '办公文档'],
  ['PDF', '文档格式'],
  ['源码', '代码工程'],
  ['成品', '可直接使用'],
  ['模板', '样板方案'],
  ['素材', '可用资源'],
  ['字体', '字库资源'],
  ['插件包', '扩展合集']
]

const TITLE_TEMPLATES = [
  (core: string) => `${core} 即用版`,
  (core: string) => `${core} 精选`,
  (core: string) => `实用｜${core}`,
  (core: string) => `${core} 可装可用`,
  (core: string) => `推荐｜${core}`,
  (core: string) => `${core} 资料齐`,
  (core: string) => `${core} 售后在`,
  (core: string) => `热销｜${core}`
]

const DESC_OPENERS = [
  '整理了一份可直接使用的内容，',
  '这份资料已按使用场景重新梳理，',
  '内容已检查可用性，',
  '面向实际使用场景准备，',
  '已按常见需求做了整理，'
]

const DESC_MIDDLES = [
  '下单后按流程交付，有问题可随时沟通。',
  '付款后尽快处理，细节可先私信确认。',
  '支持使用说明，避免踩坑。',
  '适合自学或工作使用，按需取用。',
  '说明与配套尽量写清楚，减少反复沟通。'
]

const DESC_CLOSERS = [
  '\n\n【温馨提示】图片与文案仅供参考，下单前可先问清版本/适用环境。',
  '\n\n【说明】库存与版本以沟通确认为准，满意再拍更稳妥。',
  '\n\n【售后】使用中遇到问题可留言，尽量协助处理。',
  '\n\n【备注】请按实际需求购买，避免拍错规格或版本。'
]

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function replaceWords(text: string, maxHits = 8): string {
  let out = text
  const pairs = [...WORD_PAIRS].sort(() => Math.random() - 0.5)
  let hits = 0
  for (const [a, b] of pairs) {
    if (hits >= maxHits) break
    if (out.includes(a)) {
      out = out.split(a).join(b)
      hits += 1
    }
  }
  return out
}

function stripNoise(text: string): string {
  return text
    .replace(/【[^】]{0,8}】/g, '')
    .replace(/\[[^\]]{0,8}\]/g, '')
    .replace(/[!！]{2,}/g, '！')
    .replace(/[。.]{2,}/g, '。')
    .replace(/[～~]{2,}/g, '～')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function rebuildTitle(raw: string): string {
  let core = stripNoise(raw)
  core = replaceWords(core, 6)
  // 去掉过长无意义尾巴
  core = core.replace(/(包邮|秒发|可刀|勿刀|急出)+$/g, '').trim()
  if (!core) core = '精选好物'
  // 先截短再套模板，保证最终 ≤30
  const budget = 22
  if (core.length > budget) core = core.slice(0, budget)
  let t = pick(TITLE_TEMPLATES)(core)
  t = truncateTitle(t)
  // 若模板后仍和原文高度相似，强制换一种结构
  if (t === raw || (raw.includes(t) && t.length > 10)) {
    t = truncateTitle(`实用｜${replaceWords(core, 4)}`)
  }
  return t
}

function rebuildDesc(raw: string, title: string): string {
  let body = stripNoise(raw || title)
  body = replaceWords(body, 12)
  // 按句号拆分，打乱非空短句顺序（保留信息但结构变化）
  const parts = body
    .split(/(?<=[。！？\n])/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 2)
  if (parts.length >= 3) {
    const head = parts[0]
    const mid = parts.slice(1, -1).sort(() => Math.random() - 0.5)
    const tail = parts[parts.length - 1]
    body = [head, ...mid, tail].join('')
  }
  // 去掉原贴常见硬广尾巴，换成新表述
  body = body
    .replace(/(温馨提示|说明|备注|售后)[：:].{0,80}/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  const rebuilt = `${pick(DESC_OPENERS)}${body || title}${body.endsWith('。') || body.endsWith('！') ? '' : '。'}${pick(DESC_MIDDLES)}${pick(DESC_CLOSERS)}`
  return rebuilt.replace(/\n{3,}/g, '\n\n').trim()
}

/** 高质量去重改写 */
export function rewriteShelfText(title: string, desc: string): { title: string; desc: string } {
  const srcTitle = String(title || '').trim()
  const srcDesc = String(desc || '').trim() || srcTitle
  const nextTitle = rebuildTitle(srcTitle || '精选好物')
  let nextDesc = rebuildDesc(srcDesc, nextTitle)
  // 保证描述相对原文有明显差异
  if (nextDesc === srcDesc || (srcDesc.length > 20 && nextDesc.includes(srcDesc.slice(0, 20)))) {
    nextDesc = `${pick(DESC_OPENERS)}${replaceWords(srcDesc, 10)}\n\n${pick(DESC_MIDDLES)}${pick(DESC_CLOSERS)}`
  }
  return { title: truncateTitle(nextTitle), desc: nextDesc }
}

// —— 兼容旧 shelfOptions 导出 ——
export type ShelfMarkupType = 'percent' | 'amount'

export interface ShelfOptions {
  markupEnabled: boolean
  markupType: ShelfMarkupType
  markupValue: number
  dedupText: boolean
  cropRatio: number
}

const KEY = 'xy_shelf_options_v1'

export const defaultShelfOptions = (): ShelfOptions => ({
  markupEnabled: true,
  markupType: 'percent',
  markupValue: 1,
  dedupText: true,
  cropRatio: 0.88
})

export function loadShelfOptions(): ShelfOptions {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return defaultShelfOptions()
    const o = JSON.parse(raw)
    return {
      ...defaultShelfOptions(),
      ...o,
      markupValue: Number(o.markupValue ?? 1),
      cropRatio: Math.max(0.7, Math.min(1, Number(o.cropRatio ?? 0.88)))
    }
  } catch {
    return defaultShelfOptions()
  }
}

export function saveShelfOptions(opts: ShelfOptions): void {
  localStorage.setItem(KEY, JSON.stringify(opts))
}

export function applyMarkupPrice(base: number, opts: ShelfOptions): number {
  if (!opts.markupEnabled || !Number.isFinite(base) || base <= 0) return base
  const v = Number(opts.markupValue || 0)
  const out = opts.markupType === 'amount' ? base + v : base * (1 + v / 100)
  return Math.max(0.01, Math.round(out * 100) / 100)
}
