<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAvatar,
  NButton,
  NCard,
  NDataTable,
  NDropdown,
  NEmpty,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NSelect,
  NSpace,
  NTag,
  NText,
  NTooltip,
  useMessage,
  type DataTableColumns,
  type DropdownOption
} from 'naive-ui'
import { quickBuyItem, searchItemsBulk, getPublishDetail, publishItem, transferPublishImage } from '../api/items'
import { useCollectCacheStore } from '../stores/collectCache'
import { useAccountStore } from '../stores/account'
import { toggleFavoriteFromRow, isFavorite } from '../stores/favorites'
import AccountTabs from '../components/AccountTabs.vue'
import ShelfOptionsModal from '../components/ShelfOptionsModal.vue'
import {
  applyMarkupPrice,
  loadShelfOptions,
  rewriteShelfText,
  truncateTitle,
  type ShelfOptions
} from '../utils/shelfOptions'
import { storeToRefs } from 'pinia'

const message = useMessage()
const router = useRouter()
const accountStore = useAccountStore()
const cache = useCollectCacheStore()
const { keyword, page, pageSize, total, allRows, minWant, minView, fetchCount } =
  storeToRefs(cache)
const loading = ref(false)
const shelfOptsShow = ref(false)
const shelfPending = ref<{ mode: 'quick' | 'edit' | 'batch'; rows: any[] } | null>(null)
const buying = ref(false)
const checked = ref<Array<string | number>>([])
const buyShow = ref(false)
const buyPwd = ref('')
const buyRow = ref<any>(null)
const pageSizeOptions = [20, 30, 50]
const favTick = ref(0)
const collectProgress = ref('')
const targetFetch = ref(0)
const fetchedPagesHint = ref(0)
const sortKey = ref<'default' | 'price_asc' | 'price_desc' | 'want_desc' | 'view_desc'>('default')

const sortOptions = [
  { label: '默认顺序', value: 'default' },
  { label: '价格从低到高', value: 'price_asc' },
  { label: '价格从高到低', value: 'price_desc' },
  { label: '想要人数优先', value: 'want_desc' },
  { label: '浏览量优先', value: 'view_desc' }
]

function numPrice(row: any): number {
  const raw = String(row.price ?? row.item_price ?? '').replace(/[^\d.]/g, '')
  const n = Number(raw)
  return Number.isFinite(n) ? n : 0
}

function numMetric(v: number | string): number {
  if (typeof v === 'number') return v
  const s = String(v || '')
  if (s.includes('万')) {
    const n = Number(s.replace(/[^\d.]/g, ''))
    return Number.isFinite(n) ? n * 10000 : 0
  }
  const n = Number(s.replace(/[^\d.]/g, ''))
  return Number.isFinite(n) ? n : 0
}

const sortedAllRows = computed(() => {
  const list = [...(allRows.value || [])]
  const k = sortKey.value
  if (k === 'default') return list
  list.sort((a, b) => {
    if (k === 'price_asc') return numPrice(a) - numPrice(b)
    if (k === 'price_desc') return numPrice(b) - numPrice(a)
    if (k === 'want_desc') return numMetric(wantOf(a)) - numMetric(wantOf(b))
    if (k === 'view_desc') return numMetric(viewOf(a)) - numMetric(viewOf(b))
    return 0
  })
  return list
})

const displayRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedAllRows.value.slice(start, start + pageSize.value)
})

const totalPages = computed(() =>
  total.value > 0 ? Math.max(1, Math.ceil(total.value / pageSize.value)) : 0
)

function cover(row: any): string {
  return row.main_image || row.pic_url || row.image || row.pictUrl || ''
}

function shortTitle(row: any): string {
  const t = String(row.title || row.item_title || '')
  return t.length > 24 ? `${t.slice(0, 24)}…` : t || '-'
}

function fullTitle(row: any): string {
  return String(row.title || row.item_title || '-')
}

function wantOf(row: any): number | string {
  const n = Number(row.want_num ?? row.want_count ?? NaN)
  if (!Number.isNaN(n) && n > 0) return n
  const tag = String(row.want_tag || (Array.isArray(row.tags) ? row.tags.join(' ') : '') || '')
  const m = tag.match(/(\d+(?:\.\d+)?(?:万)?)\s*人想要/)
  if (m) return m[1]
  return row.want_num ?? row.want_count ?? 0
}

function viewOf(row: any): number | string {
  const n = Number(row.view_count ?? row.viewCount ?? row.browseCnt ?? NaN)
  if (!Number.isNaN(n) && n > 0) return n
  const tag = String(
    row.browse_tag || (Array.isArray(row.tags) ? row.tags.join(' ') : '') || ''
  )
  const m = tag.match(/(\d+(?:\.\d+)?(?:万)?)\s*(?:人)?(?:浏览|看过|次浏览|次看过)/)
  if (m) return m[1]
  if (tag.includes('浏览') || tag.includes('看过')) {
    const any = tag.match(/(\d+(?:\.\d+)?(?:万)?)/)
    if (any) return any[1]
  }
  return row.view_count ?? row.viewCount ?? row.browseCnt ?? 0
}

function openItem(row: any): void {
  const id = row.item_id || row.id
  if (!id) return
  window.open(row.item_url || `https://www.goofish.com/item?id=${id}`, '_blank')
}

function openBuy(row: any): void {
  buyRow.value = row
  buyPwd.value = ''
  buyShow.value = true
}

async function confirmBuy(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  const itemId = String(buyRow.value?.item_id || buyRow.value?.id || '')
  if (!cookieId) {
    message.warning('请先选择闲鱼账号')
    return
  }
  if (!itemId) {
    message.warning('缺少商品ID')
    return
  }
  buying.value = true
  try {
    const res = await quickBuyItem({
      cookie_id: cookieId,
      item_id: itemId,
      pay_password: buyPwd.value.trim() || undefined
    })
    buyShow.value = false
    if (res?.success) {
      message.success(res.message || '购买流程已完成，请在订单页核对')
    } else if (res?.need_manual) {
      message.warning(res.message || '需手动完成支付')
      if (res.url) window.open(res.url, '_blank')
    } else {
      message.error(res?.message || '快捷购买失败')
      if (res?.url) window.open(res.url, '_blank')
    }
  } catch (e: any) {
    message.error(e?.message || '快捷购买失败（平台可能拦截自动化）')
  } finally {
    buying.value = false
  }
}

function toggleFavorite(row: any): void {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    message.warning('请先选择闲鱼账号')
    return
  }
  const { added } = toggleFavoriteFromRow(cookieId, row)
  favTick.value += 1
  message.success(added ? '已添加收藏' : '已取消收藏')
}

function opOptions(r: any): DropdownOption[] {
  void favTick.value
  const cid = accountStore.activeCookieId || ''
  const id = String(r.item_id || r.id || '')
  const fav = cid && id ? isFavorite(cid, id) : false
  return [
    { label: '打开', key: 'open' },
    { label: '快捷购买', key: 'buy' },
    { label: '编辑上架', key: 'edit_shelf' },
    { label: '一键上架', key: 'shelf' },
    { label: fav ? '取消收藏' : '添加收藏', key: 'fav' }
  ]
}

function onOp(key: string | number, r: any): void {
  if (key === 'open') openItem(r)
  else if (key === 'buy') openBuy(r)
  else if (key === 'edit_shelf') openShelfDialog('edit', [r])
  else if (key === 'shelf') openShelfDialog('quick', [r])
  else if (key === 'fav') toggleFavorite(r)
}

function openShelfDialog(mode: 'quick' | 'edit' | 'batch', list: any[]): void {
  if (!list.length) {
    message.warning('请先勾选商品')
    return
  }
  shelfPending.value = { mode, rows: list }
  shelfOptsShow.value = true
}

async function onShelfOptsConfirm(opts: ShelfOptions): Promise<void> {
  const pending = shelfPending.value
  shelfPending.value = null
  if (!pending) return
  if (pending.mode === 'quick' && pending.rows[0]) {
    await doQuickPublish(pending.rows[0], opts)
  } else if (pending.mode === 'edit' && pending.rows[0]) {
    await doGoPublish(pending.rows[0], opts)
  } else if (pending.mode === 'batch') {
    await doBatchShelf(pending.rows, opts)
  }
}

async function buildPublishDraft(row: any, opts?: ShelfOptions): Promise<Record<string, unknown>> {
  const cookieId = accountStore.activeCookieId || ''
  const itemId = String(row.item_id || row.id || '')
  const shelf = opts || loadShelfOptions()
  const parsePrice = (v: unknown): string => {
    const s = String(v ?? '')
      .replace(/[￥¥元,，\s]/g, '')
      .replace(/[^\d.]/g, '')
    return s
  }
  let draft: Record<string, unknown> = {
    title: fullTitle(row),
    price: parsePrice(row.price ?? row.item_price),
    original_price: parsePrice(row.original_price ?? row.oriPrice),
    images: [cover(row)].filter(Boolean),
    item_id: itemId,
    item_url: String(row.item_url || (itemId ? `https://www.goofish.com/item?id=${itemId}` : '')),
    desc: String(row.desc || row.description || fullTitle(row)),
    quantity: 1,
    area: String(row.area || row.city || row.location || ''),
    cookie_id: cookieId,
    shipping: 'free'
  }
  if (cookieId && itemId) {
    try {
      const res = await getPublishDetail(cookieId, itemId)
      const d = (res?.data || {}) as Record<string, unknown>
      const imgs = Array.isArray(d.images) ? (d.images as string[]).filter(Boolean) : []
      draft = {
        ...draft,
        title: String(d.title || draft.title),
        desc: String(d.desc || draft.desc),
        price: parsePrice(d.price ?? draft.price),
        original_price: parsePrice(d.original_price ?? draft.original_price),
        images: imgs.length ? imgs.slice(0, 9) : draft.images,
        quantity: Number(d.quantity || 1) || 1,
        area: String(d.area || draft.area || '')
      }
    } catch {
      // 详情失败仍用列表字段，不阻断上架
    }
  }
  const basePrice = Number(draft.price || 0)
  const marked = applyMarkupPrice(basePrice, shelf)
  draft.price = String(marked || draft.price || '')
  if (!draft.original_price && basePrice) draft.original_price = String(basePrice)
  let title = String(draft.title || '')
  let desc = String(draft.desc || '')
  if (shelf.dedupText) {
    const rw = rewriteShelfText(title, desc)
    title = rw.title
    desc = rw.desc
  }
  draft.title = truncateTitle(title)
  draft.desc = desc
  draft.dedup_text = shelf.dedupText
  draft.crop_ratio = null
  return draft
}

async function doGoPublish(row: any, opts: ShelfOptions): Promise<void> {
  message.loading('正在准备发布草稿…', { duration: 0 })
  try {
    const draft = await buildPublishDraft(row, opts)
    sessionStorage.setItem('xy_publish_draft', JSON.stringify(draft))
    sessionStorage.setItem('xy_publish_drafts', JSON.stringify([draft]))
    void router.push({ name: 'publish' })
  } catch (e: any) {
    message.warning(e?.message || '准备发布失败')
  } finally {
    message.destroyAll()
  }
}

async function doQuickPublish(row: any, opts: ShelfOptions): Promise<void> {
  const cookieId = accountStore.activeCookieId || ''
  if (!cookieId) {
    message.warning('请先选择账号')
    return
  }
  message.loading('正在一键上架…', { duration: 0 })
  try {
    const draft = await buildPublishDraft(row, opts)
    const rawImgs = (Array.isArray(draft.images) ? draft.images : []) as string[]
    const images: Array<{ url: string }> = []
    for (const u of rawImgs.slice(0, 9)) {
      const url = String(u || '')
      if (!url) continue
      try {
        if (/goofish|alicdn|taobao/i.test(url)) images.push({ url })
        else {
          const tr = await transferPublishImage(cookieId, url)
          images.push({ url: String((tr as any)?.data?.url || (tr as any)?.url || url) })
        }
      } catch {
        images.push({ url })
      }
    }
    if (!images.length) {
      message.error('没有可用图片，无法上架')
      return
    }
    await publishItem({
      cookie_id: cookieId,
      title: truncateTitle(String(draft.title || '商品')),
      desc: String(draft.desc || draft.title || ''),
      price: Number(draft.price) || 0.01,
      original_price: Number(draft.original_price) || undefined,
      quantity: Number(draft.quantity) || 1,
      images,
      shipping: 'free',
      dedup_text: !!opts.dedupText,
      crop_ratio: null
    })
    message.success('一键上架成功')
  } catch (e: any) {
    message.error(e?.message || '一键上架失败')
  } finally {
    message.destroyAll()
  }
}

async function goPublish(row: any): Promise<void> {
  openShelfDialog('edit', [row])
}

async function quickPublish(row: any): Promise<void> {
  openShelfDialog('quick', [row])
}

let searchSeq = 0

async function onSearch(resetPage = true): Promise<void> {
  if (!keyword.value.trim()) {
    message.warning('请输入关键词')
    return
  }
  if (!accountStore.activeCookieId) {
    message.warning('请先在上方选择用于采集的闲鱼账号')
    return
  }
  const want = Math.max(30, Math.min(3000, Number(fetchCount.value) || 100))
  fetchCount.value = want
  targetFetch.value = want
  if (resetPage) page.value = 1
  const seq = ++searchSeq
  loading.value = true
  // 新关键词/重新采集：先清空旧结果，避免混在一起
  cache.setResult({
    keyword: keyword.value.trim(),
    page: 1,
    pageSize: pageSize.value,
    total: 0,
    rows: [],
    minWant: minWant.value,
    minView: minView.value,
    fetchCount: want
  })
  collectProgress.value = `正在采集约 ${want} 条…`
  try {
    const res = await searchItemsBulk(keyword.value.trim(), want, {
      min_want: minWant.value,
      min_view: minView.value,
      cookie_id: accountStore.activeCookieId
    })
    if (seq !== searchSeq) return
    const list = res.data || []
    const pagesGot = Math.max(
      1,
      Number(res.fetched_pages || res.total_pages || Math.ceil(list.length / 30) || 1)
    )
    fetchedPagesHint.value = pagesGot
    cache.setResult({
      keyword: keyword.value.trim(),
      page: 1,
      pageSize: pageSize.value,
      total: list.length,
      rows: [...list],
      minWant: minWant.value,
      minView: minView.value,
      fetchCount: want
    })
    const localPages = Math.max(1, Math.ceil(list.length / pageSize.value))
    const src = String((res as any).source || '')
    collectProgress.value = `已采集 ${list.length} 条 · ${localPages} 页可翻（目标 ${want}，抓取 ${pagesGot} 页${src ? ' · ' + src : ''}）`
    if (res.error && !list.length) message.error(String(res.error))
    else if (list.length < want) {
      message.warning(
        `本次采到 ${list.length}/${want} 条。若远少于目标，请换关键词重试或确认账号在线；翻页仍可继续看已采结果`
      )
    } else message.success(`采集完成：${list.length} 条 / ${localPages} 页`)
  } catch (e: any) {
    if (seq === searchSeq) {
      collectProgress.value = ''
      message.error(e?.message || '采集失败')
    }
  } finally {
    if (seq === searchSeq) loading.value = false
  }
}

const columns: DataTableColumns<any> = [
  { type: 'selection', width: 48 },
  {
    title: '序号',
    key: 'idx',
    width: 56,
    align: 'center',
    render: (_r, i) => (page.value - 1) * pageSize.value + i + 1
  },
  {
    title: '封面',
    key: 'cover',
    width: 72,
    align: 'center',
    render: (r) => {
      const src = cover(r)
      if (!src) return '-'
      return h(NImage, {
        src,
        width: 48,
        height: 48,
        objectFit: 'cover',
        style: 'border-radius:6px'
      })
    }
  },
  {
    title: '标题',
    key: 'title',
    minWidth: 160,
    align: 'center',
    render: (r) =>
      h(
        NTooltip,
        { placement: 'top' },
        {
          trigger: () => h('span', { style: 'display:inline-block;max-width:180px' }, shortTitle(r)),
          default: () =>
            h(
              'div',
              {
                style:
                  'max-width:360px;white-space:normal;word-break:break-word;text-align:left;line-height:1.5'
              },
              fullTitle(r)
            )
        }
      )
  },
  {
    title: '现价',
    key: 'price',
    width: 80,
    align: 'center',
    render: (r) => h('span', { style: 'color:#18a058' }, String(r.price || r.item_price || '-'))
  },
  {
    title: '原价/划线价',
    key: 'original_price',
    width: 100,
    align: 'center',
    render: (r) =>
      h(
        'span',
        { style: 'color:#f0a020;text-decoration:line-through' },
        String(r.original_price || r.oriPrice || '-')
      )
  },
  {
    title: '卖家',
    key: 'seller',
    width: 110,
    align: 'center',
    render: (r) =>
      h('div', { style: 'display:flex;flex-direction:column;align-items:center;gap:4px;line-height:1.2' }, [
        r.seller_avatar || r.avatar
          ? h(NAvatar, { size: 28, round: true, src: r.seller_avatar || r.avatar })
          : null,
        h(
          'span',
          {
            style:
              'font-size:12px;max-width:96px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'
          },
          r.seller_name || r.seller || r.nick || '-'
        )
      ])
  },
  {
    title: '地区',
    key: 'area',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (r) => r.area || r.city || r.location || '-'
  },
  {
    title: '想要/浏览',
    key: 'want_view',
    width: 90,
    align: 'center',
    render: (r) =>
      h(
        'div',
        { style: 'font-size:12px;line-height:1.35;white-space:normal' },
        [h('div', `想要:${wantOf(r)}`), h('div', `浏览:${viewOf(r)}`)]
      )
  },
  {
    title: '发布时间',
    key: 'publish_time',
    width: 110,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (r) => r.publish_time || '-'
  },
  {
    title: '操作',
    key: 'op',
    width: 100,
    align: 'center',
    fixed: 'right',
    render: (r) =>
      h(
        NDropdown,
        {
          trigger: 'click',
          options: opOptions(r),
          onSelect: (k: string | number) => onOp(k, r)
        },
        () => h(NButton, { size: 'tiny' }, () => '操作')
      )
  }
]

function onPageChange(p: number): void {
  page.value = p
  // 本地切片，不再请求
}

function onPageSizeChange(ps: number): void {
  pageSize.value = ps
  page.value = 1
}

function onClear(): void {
  cache.clear()
  checked.value = []
  collectProgress.value = ''
  message.success('已清空搜索结果')
}

function onBatchShelf(): void {
  if (!checked.value.length) {
    message.warning('请先勾选商品')
    return
  }
  const selected = allRows.value.filter((r) =>
    checked.value.includes(String(r.item_id || r.id || r.title))
  )
  if (!selected.length) {
    message.warning('未找到勾选商品')
    return
  }
  openShelfDialog('batch', selected)
}

async function doBatchShelf(selected: any[], opts: ShelfOptions): Promise<void> {
  message.loading(`正在准备 ${selected.length} 个发布标签…`, { duration: 0 })
  try {
    const drafts: Record<string, unknown>[] = []
    for (const row of selected) {
      drafts.push(await buildPublishDraft(row, opts))
    }
    sessionStorage.setItem('xy_publish_drafts', JSON.stringify(drafts))
    sessionStorage.setItem('xy_publish_draft', JSON.stringify(drafts[0]))
    message.success(`已打开 ${drafts.length} 个发布标签，可逐个改信息或开启间隔批量发布`)
    void router.push({ name: 'publish' })
  } catch (e: any) {
    message.error(e?.message || '批量上架准备失败')
  } finally {
    message.destroyAll()
  }
}
</script>

<template>
  <n-card title="采集管理 · 商品搜索" size="small">
    <AccountTabs :show-unread="false" />
    <n-text depth="3" style="display: block; margin: 4px 0 8px; font-size: 12px">
      上方选中的账号用于采集 Cookie。设置「采集条数」后一次拉齐全部结果，本地翻页即时切换；不会在第 3
      页继续「冒出」更多页，当前分页数 = 已采集条数 ÷ 每页条数。
    </n-text>
    <div class="toolbar">
      <n-input
        v-model:value="keyword"
        placeholder="搜索闲鱼商品"
        style="width: 260px"
        clearable
        @keydown.enter="onSearch()"
      />
      <div class="filter-field">
        <span class="filter-label">采集条数</span>
        <n-input-number
          v-model:value="fetchCount"
          :min="30"
          :max="1200"
          :step="30"
          style="width: 140px"
        />
      </div>
      <div class="filter-field">
        <span class="filter-label">最低想要人数</span>
        <n-input-number
          v-model:value="minWant"
          :min="0"
          clearable
          placeholder="不限"
          style="width: 140px"
        />
      </div>
      <div class="filter-field">
        <span class="filter-label">最低浏览量</span>
        <n-input-number
          v-model:value="minView"
          :min="0"
          clearable
          placeholder="不限"
          style="width: 140px"
        />
      </div>
      <div class="filter-field">
        <span class="filter-label">排序</span>
        <n-select v-model:value="sortKey" :options="sortOptions" style="width: 160px" />
      </div>
      <n-button type="primary" :loading="loading" @click="onSearch()">开始采集</n-button>
      <n-button secondary :disabled="!checked.length" @click="onBatchShelf">批量上架</n-button>
      <n-text depth="3" style="font-size: 12px">上架时会弹出加价/去重设置（自动记住）</n-text>
      <n-button quaternary @click="onClear">一键清空</n-button>
      <n-button secondary @click="router.push({ name: 'favorites' })">我的收藏</n-button>
      <n-button secondary @click="router.push({ name: 'publish' })">发布商品</n-button>
      <n-tag v-if="checked.length" type="info" size="small">当前已选 {{ checked.length }} 条</n-tag>
      <n-text v-if="total > 0" depth="3" style="font-weight: 600">
        共采集 {{ total }} 条 · {{ totalPages }} 页
        <template v-if="targetFetch">（目标 {{ targetFetch }} 条）</template>
        · 当前第 {{ page }}/{{ totalPages }} 页 · 每页 {{ pageSize }}
      </n-text>
      <n-text v-else depth="3">共 0 条 · 设置采集条数后开始</n-text>
    </div>
    <n-text depth="3" style="display: block; margin-bottom: 8px; font-size: 12px">
      首次采集可能较久，完成后翻页无需再等待。若实际条数少于目标，多为闲鱼无更多结果或翻页按钮不可用。
      <span v-if="collectProgress"> · {{ collectProgress }}</span>
    </n-text>
    <n-data-table
      v-model:checked-row-keys="checked"
      :loading="loading"
      :columns="columns"
      :data="displayRows"
      size="small"
      :row-key="(r) => String(r.item_id || r.id || r.title)"
      :bordered="false"
      :scroll-x="1100"
      flex-height
      style="height: calc(100vh - 300px)"
    />
    <n-space v-if="total > 0" justify="end" style="margin-top: 12px">
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        :page-sizes="pageSizeOptions"
        show-size-picker
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </n-space>
    <n-empty v-if="!loading && !displayRows.length && !total" description="输入关键词开始采集搜索" style="margin-top: 24px" />
  </n-card>

  <n-modal v-model:show="buyShow" preset="card" title="快捷购买" style="width: 420px">
    <n-text type="warning" style="display: block; margin-bottom: 8px">
      将使用当前账号 Cookie 打开商品页尝试自动点击购买。支付宝支付常被平台拦截，失败时会打开确认页供手动完成。
    </n-text>
    <n-text depth="3" style="display: block; margin-bottom: 12px">
      {{ buyRow ? fullTitle(buyRow) : '' }}
    </n-text>
    <n-form>
      <n-form-item label="支付密码（可选）">
        <n-input
          v-model:value="buyPwd"
          type="password"
          show-password-on="click"
          placeholder="若出现支付密码框将尝试填写"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="buyShow = false">取消</n-button>
        <n-button type="primary" :loading="buying" @click="confirmBuy">确认购买</n-button>
      </n-space>
    </template>
  </n-modal>

  <ShelfOptionsModal v-model:show="shelfOptsShow" title="上架设置（加价 / 去重）" @confirm="onShelfOptsConfirm" />
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 8px;
}
.filter-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.filter-label {
  font-size: 12px;
  color: var(--n-text-color-3);
  white-space: nowrap;
}
</style>
