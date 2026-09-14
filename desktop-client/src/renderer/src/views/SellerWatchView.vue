<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAvatar,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NInputNumber,
  NPagination,
  NRadio,
  NRadioGroup,
  NSpace,
  NSwitch,
  NTag,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns,
  type DataTableRowKey
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import ShelfOptionsModal from '../components/ShelfOptionsModal.vue'
import { useAccountStore } from '../stores/account'
import { getPublishDetail, publishItem, transferPublishImage } from '../api/items'
import {
  applyMarkupPrice,
  loadShelfOptions,
  rewriteShelfText,
  truncateTitle,
  type ShelfOptions
} from '../utils/shelfOptions'
import {
  batchDeleteSellerWatches,
  bindWatchItem,
  deleteSellerWatch,
  listDropshipJobs,
  listRemoteSellerItems,
  listSellerWatches,
  listWatchItems,
  previewSellerItems,
  resolveSellerInput,
  retryDropshipBuy,
  syncSellerWatch,
  upsertSellerWatch,
  type SellerWatch,
  type SellerWatchItem
} from '../api/sellerWatch'

const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const accountStore = useAccountStore()

const loading = ref(false)
const resolving = ref(false)
const watches = ref<SellerWatch[]>([])
const selectedId = ref<number | null>(null)
const checkedKeys = ref<DataTableRowKey[]>([])
const viewMode = ref<'list' | 'products'>('list')
const mappedItems = ref<SellerWatchItem[]>([])
const mappedTotal = ref(0)
const mappedPage = ref(1)
const mappedPageSize = 20
const remoteItems = ref<any[]>([])
const remotePage = ref(1)
const remoteHasNext = ref(false)
const remoteTotal = ref(0)
const syncing = ref(false)
const dropshipJobs = ref<any[]>([])
const shelfOptsShow = ref(false)
const shelfPendingRow = ref<any>(null)
const shelfPendingMode = ref<'edit' | 'quick'>('quick')
const draftingNew = ref(false)

const form = ref({
  seller_user_id: '',
  seller_nick: '',
  enabled: true,
  follow_price: true,
  markup_type: 'percent' as 'percent' | 'amount',
  markup_value: 1,
  interval_sec: 300,
  remark: ''
})

const profile = ref<{
  nickname?: string
  avatar_url?: string
  user_id?: string
  bio?: string
  sold_count?: string
  good_rate?: string
  register_days?: string
  city?: string
} | null>(null)

const selected = computed(() => watches.value.find((w) => w.id === selectedId.value) || null)
const canUpdateSelected = computed(() => {
  if (!selected.value) return false
  const uid = String(form.value.seller_user_id || '').trim()
  return uid === String(selected.value.seller_user_id) || viewMode.value === 'products'
})

function applyMarkup(base: number): number {
  const opts = loadShelfOptions()
  const v = Number(form.value.markup_value || 0)
  if (v > 0) {
    if (form.value.markup_type === 'amount') return Math.max(0.01, Math.round((base + v) * 100) / 100)
    return Math.max(0.01, Math.round(base * (1 + v / 100) * 100) / 100)
  }
  return applyMarkupPrice(base, opts)
}

/** 仅真实头像；没有就不展示（不用 dicebear） */
function normalizeAvatar(url?: string): string {
  let u = String(url || '').trim()
  if (!u) return ''
  if (u.startsWith('//')) u = 'https:' + u
  if (!/^https?:\/\//i.test(u) && !u.startsWith('data:')) return ''
  if (/dicebear/i.test(u)) return ''
  return u
}

function fillFormFromWatch(hit: SellerWatch): void {
  form.value.seller_user_id = hit.seller_user_id
  form.value.seller_nick = hit.seller_nick || ''
  form.value.enabled = !!Number(hit.enabled ?? 1)
  form.value.follow_price = !!Number(hit.follow_price ?? 1)
  form.value.markup_type = (hit.markup_type as any) || 'percent'
  form.value.markup_value = Number(hit.markup_value || 0)
  form.value.interval_sec = Number(hit.interval_sec || 300)
  form.value.remark = hit.remark || ''
  profile.value = {
    nickname: hit.seller_nick || '',
    avatar_url: normalizeAvatar(hit.seller_avatar),
    user_id: hit.seller_user_id
  }
  draftingNew.value = false
}

function selectWatchBySellerUid(uid: string): boolean {
  const id = String(uid || '').trim()
  if (!id) return false
  const hit = watches.value.find((w) => String(w.seller_user_id) === id)
  if (!hit) return false
  selectedId.value = hit.id
  fillFormFromWatch(hit)
  return true
}

function ensureWatchSelected(): boolean {
  if (selectedId.value) return true
  const uid = String(form.value.seller_user_id || '').trim()
  return !!(uid && selectWatchBySellerUid(uid))
}

function parsePrice(v: unknown): number {
  const s = String(v ?? '')
    .replace(/[￥¥元,，\s]/g, '')
    .replace(/[^\d.]/g, '')
  const n = Number(s)
  return Number.isFinite(n) ? n : 0
}

function resetAddForm(): void {
  form.value.seller_user_id = ''
  form.value.seller_nick = ''
  form.value.remark = ''
  profile.value = null
  draftingNew.value = true
  selectedId.value = null
  remoteItems.value = []
  remotePage.value = 1
  remoteHasNext.value = false
  remoteTotal.value = 0
}

async function loadDropshipJobs(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    dropshipJobs.value = []
    return
  }
  try {
    const res = await listDropshipJobs(cid)
    dropshipJobs.value = res.data || []
  } catch {
    dropshipJobs.value = []
  }
}

async function loadWatches(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    watches.value = []
    return
  }
  loading.value = true
  try {
    const res = await listSellerWatches(cid)
    watches.value = res.data || []
    if (selectedId.value && !watches.value.some((w) => w.id === selectedId.value)) {
      selectedId.value = null
      if (viewMode.value === 'products') viewMode.value = 'list'
    }
    // 不再自动选中第一个，支持多卖家互不干扰
    await loadDropshipJobs()
  } catch (e: any) {
    message.error(e?.message || '加载监控失败')
  } finally {
    loading.value = false
  }
}

async function loadSelectedDetail(): Promise<void> {
  if (!selectedId.value) {
    mappedItems.value = []
    mappedTotal.value = 0
    remoteItems.value = []
    return
  }
  try {
    const [mapRes, remoteRes] = await Promise.all([
      listWatchItems(selectedId.value, mappedPage.value, mappedPageSize),
      listRemoteSellerItems(selectedId.value, remotePage.value)
    ])
    mappedItems.value = mapRes.data || []
    mappedTotal.value = Number(mapRes.total || 0)
    remoteItems.value = remoteRes.items || []
    remoteHasNext.value = !!remoteRes.next_page
    remoteTotal.value = Number(remoteRes.total_count || 0)
    const av = normalizeAvatar(remoteRes.seller_avatar || remoteRes.watch?.seller_avatar)
    const idx = watches.value.findIndex((w) => w.id === selectedId.value)
    if (idx >= 0) {
      const cur = { ...watches.value[idx] }
      if (av) cur.seller_avatar = av
      if (remoteRes.seller_nick) cur.seller_nick = remoteRes.seller_nick
      if (remoteRes.watch) Object.assign(cur, remoteRes.watch)
      watches.value.splice(idx, 1, cur)
      if (av && !normalizeAvatar(profile.value?.avatar_url)) {
        profile.value = {
          ...(profile.value || {}),
          avatar_url: av,
          nickname: cur.seller_nick || profile.value?.nickname,
          user_id: cur.seller_user_id
        }
      }
    }
    if (!remoteRes.success && remoteRes.message) message.warning(remoteRes.message)
  } catch (e: any) {
    message.error(e?.message || '加载卖家商品失败')
  }
}

async function enterSellerProducts(row: SellerWatch): Promise<void> {
  selectedId.value = row.id
  fillFormFromWatch(row)
  viewMode.value = 'products'
  mappedPage.value = 1
  remotePage.value = 1
  await loadSelectedDetail()
}

function backToWatchList(): void {
  viewMode.value = 'list'
  draftingNew.value = false
}

async function onMappedPageChange(p: number): Promise<void> {
  mappedPage.value = p
  if (!selectedId.value) return
  try {
    const mapRes = await listWatchItems(selectedId.value, mappedPage.value, mappedPageSize)
    mappedItems.value = mapRes.data || []
    mappedTotal.value = Number(mapRes.total || 0)
  } catch (e: any) {
    message.error(e?.message || '加载跟价映射失败')
  }
}

async function onRemotePageChange(p: number): Promise<void> {
  if (p < 1) return
  remotePage.value = p
  if (!selectedId.value) return
  try {
    const remoteRes = await listRemoteSellerItems(selectedId.value, remotePage.value)
    remoteItems.value = remoteRes.items || []
    remoteHasNext.value = !!remoteRes.next_page
    remoteTotal.value = Number(remoteRes.total_count || 0)
  } catch (e: any) {
    message.error(e?.message || '加载在售失败')
  }
}

async function onResolve(deep = false): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    message.warning('请先选择账号')
    return
  }
  const raw = form.value.seller_user_id.trim()
  if (!raw) {
    message.warning('请粘贴商品链接、个人主页或 userId')
    return
  }
  resolving.value = true
  try {
    const res = await resolveSellerInput(cid, raw, deep)
    if (!res.seller_user_id) {
      showManualSellerGuide(res.message || '解析失败', res.cleaned_url, res.item_id)
      return
    }
    form.value.seller_user_id = res.seller_user_id
    const p = res.profile || {}
    const av = normalizeAvatar(p.avatar_url)
    profile.value = {
      ...p,
      avatar_url: av,
      user_id: p.user_id || res.seller_user_id
    }
    form.value.seller_nick = p.nickname || res.item?.seller_nick || form.value.seller_nick

    if (selectWatchBySellerUid(res.seller_user_id)) {
      draftingNew.value = false
      message.success(`该卖家已在关注列表：${form.value.seller_nick || res.seller_user_id}`)
      return
    }

    // 新卖家：与当前选中的监控脱钩，防止「更新规则」改错人
    draftingNew.value = true
    selectedId.value = null
    viewMode.value = 'list'
    message.success(`已识别新卖家：${form.value.seller_nick || res.seller_user_id}，可点「添加卖家监控」`)

    remoteItems.value = []
    remotePage.value = 1
    try {
      const prev = await previewSellerItems(cid, res.seller_user_id, 1)
      remoteItems.value = prev.items || []
      remoteHasNext.value = !!prev.next_page
      remoteTotal.value = Number(prev.total_count || 0)
      const pav = normalizeAvatar(prev.seller_avatar)
      if (pav && profile.value) profile.value.avatar_url = pav
      if (prev.seller_nick && !form.value.seller_nick) form.value.seller_nick = prev.seller_nick
      if (!prev.success && prev.message) message.warning(prev.message)
      else if (!remoteItems.value.length) message.info('该卖家暂无拉到在售商品')
    } catch (pe: any) {
      message.warning(pe?.message || '预览卖家商品失败，保存后可再同步')
    }
  } catch (e: any) {
    const body = e?.body
    const detail = body && typeof body === 'object' ? (body as any).detail : null
    const tip =
      (detail && typeof detail === 'object' && detail.message) || e?.message || '解析参数失败'
    const url =
      detail && typeof detail === 'object'
        ? detail.cleaned_url ||
          (detail.item_id ? `https://www.goofish.com/item?id=${detail.item_id}` : '')
        : ''
    const itemId = detail && typeof detail === 'object' ? detail.item_id : ''
    showManualSellerGuide(String(tip), url, itemId)
  } finally {
    resolving.value = false
  }
}

function showManualSellerGuide(tip: string, itemUrl?: string, itemId?: string): void {
  const openUrl = itemUrl || (itemId ? `https://www.goofish.com/item?id=${itemId}` : '')
  dialog.warning({
    title: '需要卖家个人主页链接',
    content: () =>
      h('div', { style: 'line-height:1.7;font-size:13px;white-space:pre-wrap' }, [
        tip,
        h('div', { style: 'margin-top:10px;color:#666' }, [
          '个人主页地址类似：',
          h('code', 'https://www.goofish.com/personal?userId=数字')
        ])
      ]),
    positiveText: openUrl ? '打开商品页去复制' : '知道了',
    negativeText: openUrl ? '尝试深度识别' : '取消',
    onPositiveClick: () => {
      if (openUrl) {
        try {
          window.open(openUrl, '_blank')
        } catch {
          /* ignore */
        }
      }
    },
    onNegativeClick: () => {
      if (openUrl) void onResolve(true)
    }
  })
}

async function onAdd(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    message.warning('请先选择账号')
    return
  }
  let sellerId = form.value.seller_user_id.trim()
  if (!sellerId) {
    message.warning('请填写卖家链接或 userId')
    return
  }
  if (!/^\d{5,}$/.test(sellerId)) {
    await onResolve(false)
    sellerId = form.value.seller_user_id.trim()
    if (!/^\d{5,}$/.test(sellerId)) return
  }
  try {
    await upsertSellerWatch({
      cookie_id: cid,
      seller_user_id: sellerId,
      seller_nick: form.value.seller_nick || profile.value?.nickname || '',
      seller_avatar: normalizeAvatar(profile.value?.avatar_url),
      enabled: form.value.enabled,
      follow_price: form.value.follow_price,
      markup_type: form.value.markup_type,
      markup_value: form.value.markup_value,
      interval_sec: form.value.interval_sec,
      remark: form.value.remark
    })
    message.success('已添加卖家监控（可继续添加下一个）')
    await loadWatches()
    resetAddForm()
    viewMode.value = 'list'
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  }
}

async function onUpdateSelected(): Promise<void> {
  if (!selected.value || !canUpdateSelected.value) {
    message.warning('请先在列表点「进入商品」选中卖家，或确保输入框是当前卖家 ID')
    return
  }
  try {
    await upsertSellerWatch({
      cookie_id: selected.value.cookie_id,
      seller_user_id: selected.value.seller_user_id,
      seller_nick: form.value.seller_nick || selected.value.seller_nick,
      seller_avatar:
        normalizeAvatar(profile.value?.avatar_url) || normalizeAvatar(selected.value.seller_avatar),
      enabled: form.value.enabled,
      follow_price: form.value.follow_price,
      markup_type: form.value.markup_type,
      markup_value: form.value.markup_value,
      interval_sec: form.value.interval_sec,
      remark: form.value.remark
    })
    message.success('当前卖家规则已更新')
    await loadWatches()
  } catch (e: any) {
    message.error(e?.message || '更新失败')
  }
}

async function onDelete(row: SellerWatch): Promise<void> {
  dialog.warning({
    title: '删除监控',
    content: `确认删除监控「${row.seller_nick || row.seller_user_id}」？相关跟价映射也会移除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await deleteSellerWatch(row.id)
      if (selectedId.value === row.id) {
        selectedId.value = null
        viewMode.value = 'list'
      }
      checkedKeys.value = checkedKeys.value.filter((k) => Number(k) !== row.id)
      message.success('已删除')
      await loadWatches()
    }
  })
}

async function onBatchDelete(): Promise<void> {
  const ids = checkedKeys.value.map((k) => Number(k)).filter((n) => Number.isFinite(n) && n > 0)
  if (!ids.length) {
    message.warning('请先勾选要删除的卖家')
    return
  }
  dialog.warning({
    title: '批量删除',
    content: `确认删除选中的 ${ids.length} 个卖家监控？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteSellerWatches(ids)
        message.success(`已删除 ${res.deleted || ids.length} 个`)
        if (selectedId.value && ids.includes(selectedId.value)) {
          selectedId.value = null
          viewMode.value = 'list'
        }
        checkedKeys.value = []
        await loadWatches()
      } catch (e: any) {
        message.error(e?.message || '批量删除失败')
      }
    }
  })
}

async function onSync(): Promise<void> {
  if (!selectedId.value) return
  syncing.value = true
  try {
    const res = await syncSellerWatch(selectedId.value)
    message.success(res.message || '同步完成')
    await Promise.all([loadWatches(), loadSelectedDetail()])
  } catch (e: any) {
    message.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function buildShelfDraft(row: any, opts?: ShelfOptions): Promise<Record<string, unknown>> {
  const cid = accountStore.activeCookieId || ''
  const itemId = String(row.item_id || '')
  const shelf = opts || loadShelfOptions()
  const base = parsePrice(row.price)
  const price = shelf.markupEnabled
    ? applyMarkupPrice(base, {
        ...shelf,
        markupType: form.value.markup_type,
        markupValue: Number(form.value.markup_value || shelf.markupValue)
      })
    : base
  let draft: Record<string, unknown> = {
    title: row.title || '',
    price: String(price),
    original_price: String(row.original_price || base || ''),
    images: [row.pic_url || row.item_pic].filter(Boolean),
    item_id: itemId,
    item_url: row.web_url || `https://www.goofish.com/item?id=${itemId}`,
    desc: row.title || '',
    quantity: 1,
    cookie_id: cid,
    shipping: 'free',
    watch_id: selectedId.value,
    source_item_id: itemId,
    dropship: true
  }
  if (cid && itemId) {
    try {
      const res = await getPublishDetail(cid, itemId)
      const d = (res?.data || {}) as Record<string, unknown>
      const imgs = Array.isArray(d.images) ? (d.images as string[]).filter(Boolean) : []
      draft = {
        ...draft,
        title: String(d.title || draft.title),
        desc: String(d.desc || draft.desc),
        images: imgs.length ? imgs.slice(0, 9) : draft.images,
        quantity: Number(d.quantity || 1) || 1,
        original_price: String(d.original_price || draft.original_price || '')
      }
    } catch {
      /* ignore */
    }
  }
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

function openShelfForRow(row: any, mode: 'edit' | 'quick'): void {
  if (!ensureWatchSelected()) {
    message.warning('请先添加该卖家监控，或点「进入商品」')
    return
  }
  if (mode === 'edit') {
    void doEditShelfRemote(row, {
      ...loadShelfOptions(),
      dedupText: true,
      cropRatio: 0.9,
      markupEnabled: true
    })
    return
  }
  shelfPendingRow.value = row
  shelfPendingMode.value = mode
  shelfOptsShow.value = true
}

async function onShelfOptsConfirm(opts: ShelfOptions): Promise<void> {
  const row = shelfPendingRow.value
  shelfPendingRow.value = null
  if (!row) return
  if (shelfPendingMode.value === 'edit') await doEditShelfRemote(row, opts)
  else await doQuickShelfRemote(row, opts)
}

async function doEditShelfRemote(row: any, opts: ShelfOptions): Promise<void> {
  message.loading('准备发布草稿…', { duration: 0 })
  try {
    const draft = await buildShelfDraft(row, { ...opts, dedupText: false })
    draft.dedup_text = true
    draft.dedupText = true
    draft.crop_ratio = null
    draft.origin_title = draft.title
    draft.origin_desc = draft.desc
    sessionStorage.setItem('xy_publish_draft', JSON.stringify(draft))
    sessionStorage.setItem('xy_publish_drafts', JSON.stringify([draft]))
    void router.push({ name: 'publish' })
  } finally {
    message.destroyAll()
  }
}

async function doQuickShelfRemote(row: any, opts: ShelfOptions): Promise<void> {
  const cid = accountStore.activeCookieId || ''
  if (!cid) {
    message.warning('请先选择账号')
    return
  }
  if (!ensureWatchSelected()) {
    message.warning('请先保存或进入该卖家商品区')
    return
  }
  message.loading('正在一键上架…', { duration: 0 })
  try {
    const draft = await buildShelfDraft(row, opts)
    const rawImgs = (Array.isArray(draft.images) ? draft.images : []) as string[]
    const images: Array<{ url: string }> = []
    for (const u of rawImgs.slice(0, 9)) {
      const url = String(u || '')
      if (!url) continue
      try {
        if (/goofish|alicdn|taobao/i.test(url)) {
          images.push({ url })
        } else {
          const tr = await transferPublishImage(cid, url)
          const nu = String((tr as any)?.data?.url || (tr as any)?.url || url)
          images.push({ url: nu })
        }
      } catch {
        images.push({ url })
      }
    }
    if (!images.length) {
      message.error('没有可用图片，无法上架')
      return
    }
    const res = await publishItem({
      cookie_id: cid,
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
    const localId = String((res as any)?.data?.item_id || (res as any)?.item_id || '')
    if (localId && selectedId.value) {
      await bindWatchItem(selectedId.value, {
        source_item_id: String(row.item_id || ''),
        local_item_id: localId,
        source_title: String(row.title || ''),
        last_source_price: String(row.price || ''),
        dropship: 0
      })
      message.success(`已上架并绑定跟价：${localId}`)
      await loadSelectedDetail()
    } else {
      message.success('已提交上架')
    }
  } catch (e: any) {
    message.error(e?.message || '一键上架失败')
  } finally {
    message.destroyAll()
  }
}

async function editShelfRemote(row: any): Promise<void> {
  openShelfForRow(row, 'edit')
}

async function quickShelfRemote(row: any): Promise<void> {
  openShelfForRow(row, 'quick')
}

async function bindLocal(row: SellerWatchItem): Promise<void> {
  if (!selectedId.value) return
  const localId = window.prompt('输入你已上架的本地商品 ID（闲鱼商品编号）', row.local_item_id || '')
  if (!localId) return
  dialog.info({
    title: '是否开启代采代发？',
    content:
      '开启后：买家付款 → 自动向上家快捷购买 → 上家发货/卡密信息转发给你的买家。（支付宝常需人工确认支付）',
    positiveText: '开启代发并绑定',
    negativeText: '仅绑定（不代发）',
    onPositiveClick: async () => {
      await bindWatchItem(selectedId.value!, {
        source_item_id: row.source_item_id,
        local_item_id: localId.trim(),
        source_title: row.source_title,
        last_source_price: row.last_source_price,
        dropship: 1
      })
      message.success('已绑定并开启代发')
      await loadSelectedDetail()
    },
    onNegativeClick: async () => {
      await bindWatchItem(selectedId.value!, {
        source_item_id: row.source_item_id,
        local_item_id: localId.trim(),
        source_title: row.source_title,
        last_source_price: row.last_source_price,
        dropship: 0
      })
      message.success('已绑定')
      await loadSelectedDetail()
    }
  })
}

async function toggleDropship(row: SellerWatchItem): Promise<void> {
  if (!selectedId.value || !row.local_item_id) {
    message.warning('请先绑定本地商品')
    return
  }
  const next = !Number(row.dropship)
  await bindWatchItem(selectedId.value, {
    source_item_id: row.source_item_id,
    local_item_id: String(row.local_item_id),
    source_title: row.source_title,
    last_source_price: row.last_source_price,
    dropship: next ? 1 : 0
  })
  message.success(next ? '已开启代发' : '已关闭代发')
  await loadSelectedDetail()
}

async function onRetryBuy(job: any): Promise<void> {
  try {
    const res = await retryDropshipBuy(Number(job.id))
    message.success((res as any).message || '已重试购买')
    await loadDropshipJobs()
  } catch (e: any) {
    message.error(e?.message || '重试失败')
  }
}

const watchColumns: DataTableColumns<SellerWatch> = [
  { type: 'selection', width: 48 },
  {
    title: '头像',
    key: 'avatar',
    width: 64,
    align: 'center',
    render: (r) => {
      const src = normalizeAvatar(r.seller_avatar)
      if (!src) return '-'
      return h(NAvatar, { src, round: true, size: 36 })
    }
  },
  {
    title: '卖家',
    key: 'seller',
    minWidth: 160,
    render: (r) =>
      h('div', { style: 'line-height:1.35' }, [
        h('div', { style: 'font-weight:600' }, r.seller_nick || '-'),
        h('div', { style: 'font-size:12px;color:#888' }, `ID ${r.seller_user_id}`)
      ])
  },
  {
    title: '加价',
    key: 'markup',
    width: 90,
    render: (r) => (r.markup_type === 'amount' ? `+¥${r.markup_value}` : `+${r.markup_value}%`)
  },
  {
    title: '跟价',
    key: 'follow',
    width: 64,
    render: (r) => (Number(r.follow_price) ? '开' : '关')
  },
  {
    title: '间隔',
    key: 'interval_sec',
    width: 72,
    render: (r) => `${r.interval_sec || 300}s`
  },
  {
    title: '在售',
    key: 'remote_item_count',
    width: 72,
    render: (r) => {
      const n = Number(r.remote_item_count ?? r.item_count ?? 0)
      return Number.isFinite(n) && n > 0 ? String(n) : '-'
    }
  },
  {
    title: '上次同步',
    key: 'last_sync_at',
    width: 150,
    render: (r) => r.last_sync_at || '-'
  },
  {
    title: '操作',
    key: 'op',
    width: 180,
    render: (r) =>
      h(NSpace, { size: 6 }, () => [
        h(
          NButton,
          { size: 'tiny', type: 'primary', onClick: () => void enterSellerProducts(r) },
          () => '进入商品'
        ),
        h(
          NButton,
          { size: 'tiny', type: 'error', secondary: true, onClick: () => void onDelete(r) },
          () => '删除'
        )
      ])
  }
]

const remoteColumns: DataTableColumns<any> = [
  {
    title: '图',
    key: 'pic',
    width: 56,
    render: (r) =>
      h(NImage, {
        src: String(r.pic_url || r.item_pic || ''),
        width: 40,
        height: 40,
        objectFit: 'cover',
        lazy: true,
        style: 'border-radius:4px',
        fallbackSrc: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"/>'
      })
  },
  {
    title: '商品名称',
    key: 'title',
    ellipsis: { tooltip: true },
    render: (r) =>
      h(
        'a',
        {
          href: String(r.web_url || `https://www.goofish.com/item?id=${r.item_id || ''}`),
          target: '_blank',
          style: 'color: var(--n-primary-color)'
        },
        String(r.title || r.item_id || '-')
      )
  },
  {
    title: '现价',
    key: 'price',
    width: 80,
    render: (r) => h('span', { style: 'color:#18a058' }, String(r.price || '-'))
  },
  {
    title: '原价',
    key: 'original_price',
    width: 80,
    render: (r) =>
      h(
        'span',
        { style: 'color:#f0a020; text-decoration: line-through' },
        String(r.original_price || '-')
      )
  },
  {
    title: '加价后',
    key: 'marked',
    width: 80,
    render: (r) => {
      const base = parsePrice(r.price)
      return base ? `¥${applyMarkup(base)}` : '-'
    }
  },
  {
    title: '分类',
    key: 'category',
    width: 90,
    ellipsis: { tooltip: true },
    render: (r) => r.item_category || r.category || '-'
  },
  {
    title: '想要',
    key: 'want_num',
    width: 60,
    render: (r) => r.want_num || '-'
  },
  {
    title: '操作',
    key: 'op',
    width: 168,
    render: (r) =>
      h(NSpace, { size: 4 }, () => [
        h(NButton, { size: 'tiny', onClick: () => void editShelfRemote(r) }, () => '编辑上架'),
        h(
          NButton,
          { size: 'tiny', type: 'primary', onClick: () => void quickShelfRemote(r) },
          () => '一键上架'
        )
      ])
  }
]

/** 仅展示已一键上架/已绑定本地的跟价商品 */
const mappedBoundItems = computed(() =>
  (mappedItems.value || []).filter((r) => String(r.local_item_id || '').trim())
)

const mappedColumns: DataTableColumns<SellerWatchItem> = [
  {
    title: '对方商品',
    key: 'source_title',
    ellipsis: { tooltip: true },
    render: (r) => r.source_title || r.source_item_id
  },
  { title: '对方价', key: 'last_source_price', width: 90 },
  {
    title: '我的商品ID',
    key: 'local_item_id',
    width: 140,
    render: (r) => r.local_item_id || '-'
  },
  { title: '我的售价', key: 'last_local_price', width: 90 },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (r) => {
      const s = String(r.status || '').toLowerCase()
      if (s === 'local_off' || s === 'off_source')
        return h(NTag, { size: 'small', type: 'error' }, () => '对方已下架')
      if (s === 'synced') return h(NTag, { size: 'small', type: 'success' }, () => '已跟价')
      if (s === 'new') return h(NTag, { size: 'small', type: 'info' }, () => '新品待跟')
      if (s === 'watching') return h(NTag, { size: 'small', type: 'default' }, () => '跟价中')
      return h(NTag, { size: 'small' }, () => '跟价中')
    }
  }
]

onMounted(() => void loadWatches())
watch(
  () => accountStore.activeCookieId,
  () => {
    selectedId.value = null
    profile.value = null
    viewMode.value = 'list'
    draftingNew.value = false
    checkedKeys.value = []
    void loadWatches()
  }
)
</script>

<template>
  <n-space vertical :size="14">
    <n-card title="卖家监控 · 跟价 / 跟下架" size="small">
      <AccountTabs @change="loadWatches" />
      <n-text depth="3" style="display: block; margin: 8px 0 12px; font-size: 12px">
        支持同时关注多个卖家。识别后点「添加卖家监控」；点「进入商品」查看在售与「已上架跟价商品」。列表页只管理关注卖家，商品跟价映射在进入后查看。
      </n-text>

      <n-form label-placement="left" label-width="110" style="max-width: 860px">
        <n-form-item label="卖家链接/ID">
          <n-space style="width: 100%" :wrap="false">
            <n-input
              v-model:value="form.seller_user_id"
              placeholder="优先 personal?userId=… / 也可商品链接 / 纯数字 ID"
              style="flex: 1; min-width: 320px"
            />
            <n-button :loading="resolving" secondary type="primary" @click="() => onResolve(false)">
              识别链接
            </n-button>
          </n-space>
        </n-form-item>
        <n-form-item v-if="profile" label="卖家资料">
          <n-space align="center" :size="12">
            <n-avatar
              v-if="normalizeAvatar(profile.avatar_url)"
              :src="normalizeAvatar(profile.avatar_url)"
              round
              :size="48"
            />
            <n-space vertical :size="2">
              <n-text strong>{{ profile.nickname || '未知昵称' }}</n-text>
              <n-text depth="3" style="font-size: 12px">
                ID {{ profile.user_id || form.seller_user_id }}
                <template v-if="profile.city"> · {{ profile.city }}</template>
                <template v-if="profile.register_days"> · 来闲鱼 {{ profile.register_days }}</template>
                <template v-if="profile.sold_count"> · 卖出 {{ profile.sold_count }}</template>
                <template v-if="profile.good_rate"> · 好评 {{ profile.good_rate }}</template>
              </n-text>
              <n-text v-if="!normalizeAvatar(profile.avatar_url)" depth="3" style="font-size: 12px">
                暂未获取到头像（有头像才会显示）
              </n-text>
            </n-space>
          </n-space>
        </n-form-item>
        <n-form-item label="备注昵称">
          <n-input v-model:value="form.seller_nick" placeholder="方便辨认，识别后会自动填" />
        </n-form-item>
        <n-form-item label="加价规则">
          <n-space align="center">
            <n-radio-group v-model:value="form.markup_type" name="markup">
              <n-radio value="percent">按比例 %</n-radio>
              <n-radio value="amount">按金额 ¥</n-radio>
            </n-radio-group>
            <n-input-number v-model:value="form.markup_value" :min="0" :precision="2" style="width: 120px" />
            <n-switch v-model:value="form.follow_price" />
            <n-text depth="3">开启跟价</n-text>
          </n-space>
        </n-form-item>
        <n-form-item label="轮询间隔(秒)">
          <n-input-number v-model:value="form.interval_sec" :min="60" :step="30" style="width: 140px" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
      </n-form>
      <n-space>
        <n-button type="primary" @click="onAdd">添加卖家监控</n-button>
        <n-button v-if="canUpdateSelected" secondary @click="onUpdateSelected">更新当前规则</n-button>
        <n-button v-if="viewMode === 'products' && selected" type="info" :loading="syncing" @click="onSync">
          立即同步
        </n-button>
        <n-button quaternary @click="resetAddForm">清空表单（加下一个）</n-button>
      </n-space>
      <n-text v-if="draftingNew" depth="3" style="display: block; margin-top: 8px; font-size: 12px">
        当前是新卖家草稿，点「添加卖家监控」才会写入列表，不会覆盖已有卖家。
      </n-text>
    </n-card>

    <n-card v-if="viewMode === 'list'" title="已关注卖家" size="small" :loading="loading">
      <n-space align="center" style="margin-bottom: 10px" justify="space-between">
        <n-text>已关注 {{ watches.length }} 个卖家</n-text>
        <n-space>
          <n-button size="small" type="error" secondary :disabled="!checkedKeys.length" @click="onBatchDelete">
            批量删除{{ checkedKeys.length ? `（${checkedKeys.length}）` : '' }}
          </n-button>
          <n-button size="small" quaternary @click="loadWatches">刷新</n-button>
        </n-space>
      </n-space>
      <n-data-table
        v-model:checked-row-keys="checkedKeys"
        :columns="watchColumns"
        :data="watches"
        size="small"
        :bordered="true"
        :row-key="(r) => r.id"
        :scroll-x="900"
        :max-height="420"
      />
    </n-card>

    <template v-if="viewMode === 'products' && selected">
      <n-space align="center">
        <n-button secondary @click="backToWatchList">← 返回卖家列表</n-button>
        <n-text strong>
          {{ selected.seller_nick || '卖家' }}（{{ selected.seller_user_id }}）商品区
        </n-text>
        <n-avatar
          v-if="normalizeAvatar(selected.seller_avatar)"
          :src="normalizeAvatar(selected.seller_avatar)"
          round
          :size="28"
        />
      </n-space>

      <n-card title="对方在售（可一键上架）" size="small">
        <n-data-table
          :columns="remoteColumns"
          :data="remoteItems"
          size="small"
          :bordered="true"
          :scroll-x="900"
          :max-height="360"
        />
        <n-space justify="end" align="center" style="margin-top: 10px">
          <n-text depth="3" style="font-size: 12px">
            第 {{ remotePage }} 页 · 本页 {{ remoteItems.length }} 条
            <template v-if="remoteTotal"> · 约 {{ remoteTotal }} </template>
          </n-text>
          <n-button size="small" :disabled="remotePage <= 1" @click="onRemotePageChange(remotePage - 1)">
            上一页
          </n-button>
          <n-button size="small" :disabled="!remoteHasNext" @click="onRemotePageChange(remotePage + 1)">
            下一页
          </n-button>
        </n-space>
      </n-card>

      <n-card title="已上架跟价商品（一键上架后才会出现）" size="small">
        <n-text depth="3" style="display: block; margin-bottom: 8px; font-size: 12px">
          对上方「对方在售」点「一键上架」后，这里会显示你这边商品与对方的跟价关系；对方下架会标红。
        </n-text>
        <n-data-table
          :columns="mappedColumns"
          :data="mappedBoundItems"
          size="small"
          :bordered="true"
          :scroll-x="800"
          :max-height="360"
        />
        <n-text v-if="!mappedBoundItems.length" depth="3" style="display: block; margin-top: 8px; font-size: 12px">
          暂无已上架跟价商品
        </n-text>
        <n-space v-if="mappedTotal > mappedPageSize" justify="end" style="margin-top: 10px">
          <n-pagination
            :page="mappedPage"
            :page-size="mappedPageSize"
            :item-count="mappedTotal"
            size="small"
            @update:page="onMappedPageChange"
          />
        </n-space>
      </n-card>
    </template>

    <ShelfOptionsModal
      v-model:show="shelfOptsShow"
      title="一键上架设置（加价 / 去重）"
      @confirm="onShelfOptsConfirm"
    />
  </n-space>
</template>
