<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NCheckbox,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NText,
  NTooltip,
  NDatePicker,
  useMessage
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  getPublishDefaultLocation,
  publishItem,
  recommendPublishCategory,
  transferPublishImage,
  uploadPublishImageBase64
} from '../api/items'
import { bindWatchItem } from '../api/sellerWatch'
import { rewriteShelfText, truncateTitle } from '../utils/shelfOptions'

interface ImgItem {
  url: string
  width?: number
  height?: number
  localPreview?: string
  pending?: boolean
}

interface CategoryOpt {
  catId?: string
  catName?: string
  channelCatId?: string
  tbCatId?: string
  source?: string
  propertyId?: string | number
  propertyName?: string
}

interface PublishDraft {
  key: string
  label: string
  title: string
  desc: string
  price: number | null
  originalPrice: number | null
  quantity: number
  images: ImgItem[]
  shipping: string
  postPrice: number | null
  canSelfPickup: boolean
  locationText: string
  location: Record<string, unknown> | null
  category: CategoryOpt | null
  categoryOptions: CategoryOpt[]
  sourceUrl: string
  sourceId: string
  watchId: number | null
  dropship: boolean
  scheduleEnabled: boolean
  scheduleTime: number | null
  /** 自动去重：发布前改写文案 + 轻度裁图 */
  dedupText: boolean
  cropRatio: number
  /** 去重前原文，取消勾选时还原 */
  originTitle: string
  originDesc: string
}

const message = useMessage()
const router = useRouter()
const accountStore = useAccountStore()

const drafts = ref<PublishDraft[]>([])
const activeKey = ref('')
const intervalSec = ref(30)
const intervalEnabled = ref(true) // 多标签默认按间隔发全部
const publishing = ref(false)
const uploading = ref(false)
const loadingLoc = ref(false)
const loadingCat = ref(false)
const transferring = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const batchProgress = ref('')
const transferTip = ref('')

const shippingOptions = [
  { label: '包邮', value: 'free' },
  { label: '按距离计费', value: 'distance' },
  { label: '运费一口价', value: 'fixed' },
  { label: '无需邮寄', value: 'none' }
]

const current = computed(() => drafts.value.find((d) => d.key === activeKey.value) || null)
const canAddImage = computed(() => (current.value?.images.length || 0) < 9)
const isBatch = computed(() => drafts.value.length > 1)
const categorySelectOptions = computed(() =>
  (current.value?.categoryOptions || []).map((op) => ({
    label: op.catName || op.channelCatId || op.catId || '未命名类目',
    value: String(op.channelCatId || op.catId || op.catName || '')
  }))
)
const selectedCategoryValue = computed({
  get: () => {
    const c = current.value?.category
    if (!c) return null
    return String(c.channelCatId || c.catId || c.catName || '') || null
  },
  set: (v: string | null) => {
    if (!current.value) return
    if (!v) {
      current.value.category = null
      return
    }
    const found = (current.value.categoryOptions || []).find(
      (op) => String(op.channelCatId || op.catId || op.catName || '') === v
    )
    // 禁止把类目名当成 catId 提交（会触发「类目不存在/不是叶子类目」）
    if (found && (found.catId || found.channelCatId)) {
      current.value.category = found
    } else if (found) {
      current.value.category = found
    } else {
      current.value.category = null
    }
  }
})

function emptyDraft(partial?: Partial<PublishDraft>, idx = 0): PublishDraft {
  return {
    key: partial?.key || `draft-${Date.now()}-${idx}`,
    label: partial?.label || `商品 ${idx + 1}`,
    title: '',
    desc: '',
    price: null,
    originalPrice: null,
    quantity: 1,
    images: [],
    shipping: 'free',
    postPrice: null,
    canSelfPickup: false,
    locationText: '',
    location: null,
    category: null,
    categoryOptions: [],
    sourceUrl: '',
    sourceId: '',
    watchId: null,
    dropship: true,
    scheduleEnabled: false,
    scheduleTime: null,
    dedupText: false,
    cropRatio: 0.88,
    originTitle: '',
    originDesc: '',
    ...partial
  }
}

function parsePrice(v: unknown): number | null {
  if (v == null || v === '') return null
  if (typeof v === 'number' && !Number.isNaN(v)) return v
  const s = String(v)
    .replace(/[￥¥元,，\s]/g, '')
    .replace(/[^\d.]/g, '')
  if (!s) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

function draftFromRaw(d: Record<string, unknown>, idx: number): PublishDraft {
  const imgs: ImgItem[] = []
  if (Array.isArray(d.images)) {
    for (const u of d.images) {
      if (!u) continue
      if (typeof u === 'string') imgs.push({ url: u, localPreview: u })
      else if (typeof u === 'object' && u) {
        const o = u as Record<string, unknown>
        const url = String(o.url || o.localPreview || '')
        if (url) {
          imgs.push({
            url,
            width: Number(o.width) || undefined,
            height: Number(o.height) || undefined,
            localPreview: String(o.localPreview || url)
          })
        }
      }
    }
  } else if (d.main_image) {
    imgs.push({ url: String(d.main_image), localPreview: String(d.main_image) })
  }
  const title = String(d.title || '')
  const desc = String(d.desc || d.title || '')
  const wantDedup = !!(d.dedup_text || d.dedupText || d.auto_dedup)
  return emptyDraft(
    {
      key: String(d.item_id || d.key || `draft-${Date.now()}-${idx}`),
      label: title ? (title.length > 12 ? `${title.slice(0, 12)}…` : title) : `商品 ${idx + 1}`,
      title,
      desc,
      price: parsePrice(d.price),
      originalPrice: parsePrice(d.original_price),
      quantity: Math.max(1, Number(d.quantity || 1) || 1),
      images: imgs.slice(0, 9),
      shipping: String(d.shipping || 'free'),
      sourceUrl: String(d.item_url || ''),
      sourceId: String(d.source_item_id || d.item_id || ''),
      watchId: d.watch_id != null && d.watch_id !== '' ? Number(d.watch_id) : null,
      dropship: d.dropship === false || d.dropship === 0 || d.dropship === '0' ? false : true,
      locationText: String(d.area || ''),
      location: (d.location as Record<string, unknown>) || null,
      category: (d.category as CategoryOpt) || null,
      categoryOptions: Array.isArray(d.category_options)
        ? (d.category_options as CategoryOpt[])
        : [],
      dedupText: wantDedup,
      cropRatio: Number(d.crop_ratio ?? d.cropRatio ?? 0.88) || 0.88,
      originTitle: title,
      originDesc: desc
    },
    idx
  )
}

function loadDrafts(): void {
  try {
    const multi = sessionStorage.getItem('xy_publish_drafts')
    if (multi) {
      const arr = JSON.parse(multi) as Record<string, unknown>[]
      if (Array.isArray(arr) && arr.length) {
        drafts.value = arr.map((d, i) => draftFromRaw(d, i))
        activeKey.value = drafts.value[0].key
        intervalEnabled.value = drafts.value.length > 1
        if (arr[0]?.cookie_id) accountStore.setActive(String(arr[0].cookie_id))
        return
      }
    }
    const raw = sessionStorage.getItem('xy_publish_draft')
    if (raw) {
      const d = JSON.parse(raw) as Record<string, unknown>
      drafts.value = [draftFromRaw(d, 0)]
      activeKey.value = drafts.value[0].key
      intervalEnabled.value = false
      if (d.cookie_id) accountStore.setActive(String(d.cookie_id))
      return
    }
  } catch {
    /* ignore */
  }
  drafts.value = [emptyDraft({}, 0)]
  activeKey.value = drafts.value[0].key
  intervalEnabled.value = false
}

function persistDrafts(): void {
  try {
    const payload = drafts.value.map((d) => ({
      key: d.key,
      title: d.title,
      desc: d.desc,
      price: d.price,
      original_price: d.originalPrice,
      quantity: d.quantity,
      images: (d.images || []).map((im) => ({
        url: im.url,
        width: im.width,
        height: im.height,
        localPreview: im.localPreview
      })),
      shipping: d.shipping,
      post_price: d.postPrice,
      can_self_pickup: d.canSelfPickup,
      area: d.locationText,
      location: d.location,
      category: d.category,
      category_options: Array.isArray(d.categoryOptions) ? d.categoryOptions.slice(0, 40) : [],
      item_url: d.sourceUrl,
      item_id: d.sourceId,
      source_item_id: d.sourceId,
      watch_id: d.watchId,
      dropship: d.dropship,
      cookie_id: accountStore.activeCookieId,
      dedup_text: d.dedupText,
      crop_ratio: d.cropRatio,
      origin_title: d.originTitle,
      origin_desc: d.originDesc,
      schedule_enabled: d.scheduleEnabled,
      schedule_time: d.scheduleTime
    }))
    sessionStorage.setItem('xy_publish_drafts', JSON.stringify(payload))
    if (payload.length === 1) {
      sessionStorage.setItem('xy_publish_draft', JSON.stringify(payload[0]))
    }
  } catch (e) {
    console.warn('persistDrafts failed', e)
  }
}

function ensureDraft(): void {
  if (!drafts.value.length) {
    drafts.value = [emptyDraft({}, 0)]
    activeKey.value = drafts.value[0].key
  }
}

function clearForm(): void {
  try {
    const cur = current.value
    const keepKey = cur?.key || `draft-${Date.now()}`
    const keepLabel = cur?.label || '商品 1'
    const keepLoc = cur?.location || null
    const keepText = cur?.locationText || ''
    // 整份替换，避免 Object.assign 把响应式对象弄坏导致整页白屏
    const blank = emptyDraft(
      {
        key: keepKey,
        label: keepLabel,
        location: keepLoc,
        locationText: keepText
      },
      0
    )
    if (drafts.value.length === 0) {
      drafts.value = [blank]
    } else {
      const idx = drafts.value.findIndex((d) => d.key === activeKey.value)
      if (idx >= 0) drafts.value.splice(idx, 1, blank)
      else drafts.value = [blank]
    }
    activeKey.value = blank.key
    persistDrafts()
    void nextTick(() => message.success('已清空当前商品表单'))
  } catch (e: any) {
    console.error('clearForm failed', e)
    drafts.value = [emptyDraft({}, 0)]
    activeKey.value = drafts.value[0].key
    message.warning('清空时出现异常，已重置为空白表单')
  }
}

function applyDedupToDraft(draft: PublishDraft, on: boolean): void {
  if (on) {
    if (!draft.originTitle && !draft.originDesc) {
      draft.originTitle = draft.title
      draft.originDesc = draft.desc
    }
    const baseTitle = draft.originTitle || draft.title
    const baseDesc = draft.originDesc || draft.desc
    const rw = rewriteShelfText(baseTitle, baseDesc)
    draft.title = truncateTitle(rw.title)
    draft.desc = rw.desc
    draft.dedupText = true
    if (!draft.cropRatio || draft.cropRatio >= 1) draft.cropRatio = 0.88
  } else {
    draft.dedupText = false
    if (draft.originTitle || draft.originDesc) {
      draft.title = draft.originTitle || draft.title
      draft.desc = draft.originDesc || draft.desc
    }
  }
  persistDrafts()
}

function onDedupToggle(checked: boolean): void {
  if (!current.value) return
  applyDedupToDraft(current.value, checked)
}

function runAutoDedupOnce(): void {
  if (!current.value) return
  // 每次点击重新随机改写，方便多试几版
  if (!current.value.originTitle && !current.value.originDesc) {
    current.value.originTitle = current.value.title
    current.value.originDesc = current.value.desc
  } else {
    // 基于原文再改一版，而不是叠改
    current.value.title = current.value.originTitle
    current.value.desc = current.value.originDesc
  }
  applyDedupToDraft(current.value, true)
  message.success('已自动去重：标题/描述已重组改写，发布时图片也会二次处理')
}

function formatLoc(loc: Record<string, unknown> | null): string {
  if (!loc) return ''
  return `${loc.prov || ''}${loc.city || ''}${loc.area || ''} ${loc.poiName || ''}`.trim()
}

/** 手动填写所在地文本时，同步成可提交的 location 结构 */
function onLocationTextInput(text: string): void {
  if (!current.value) return
  const v = (text || '').trim()
  current.value.locationText = text
  if (!v) {
    current.value.location = null
    return
  }
  const prev = current.value.location || {}
  // 已有完整接口地址且文案一致时不覆盖
  if (prev.divisionId && formatLoc(prev) === v) return
  current.value.location = {
    ...prev,
    area: String(prev.area || ''),
    city: String(prev.city || v),
    divisionId: String(prev.divisionId || ''),
    gps: String(prev.gps || '116.397128,39.916527'),
    poiId: String(prev.poiId || ''),
    poiName: String(prev.poiName || v),
    prov: String(prev.prov || ''),
    manual: true
  }
}

async function loadRecommendCategory(silent = false): Promise<void> {
  const cid = accountStore.activeCookieId
  const draft = current.value
  if (!cid || !draft) {
    if (!silent) message.warning('请先选择发布账号')
    return
  }
  const title = draft.title.trim() || draft.desc.trim().split(/\r?\n/)[0]?.trim() || ''
  const imgs = draft.images.filter((im) => im.url && !im.pending)
  if (!title && !imgs.length) {
    if (!silent) message.warning('请先填写标题/描述或上传图片后再推荐类目')
    return
  }
  loadingCat.value = true
  try {
    const res = await recommendPublishCategory({
      cookie_id: cid,
      title,
      desc: draft.desc.trim(),
      images: imgs.map((im) => ({
        url: im.url,
        width: im.width || 800,
        height: im.height || 600
      }))
    })
    const options = (res?.data?.options || []) as CategoryOpt[]
    const predict = (res?.data?.predict || {}) as CategoryOpt
    draft.categoryOptions = options
    if (!draft.category && (predict.catId || predict.channelCatId || predict.catName)) {
      draft.category = predict
    } else if (!draft.category && options.length) {
      draft.category = options[0]
    }
    persistDrafts()
    if (!silent) {
      message.success(
        draft.category?.catName
          ? `已推荐类目：${draft.category.catName}`
          : options.length
            ? `已获取 ${options.length} 个可选类目`
            : '未获取到类目，发布时会自动推荐'
      )
    }
  } catch (e: any) {
    if (!silent) message.warning(e?.message || '类目推荐失败')
  } finally {
    loadingCat.value = false
  }
}

async function loadDefaultLocation(applyAll = false, silent = false): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    if (!silent) message.warning('请先选择发布账号')
    return
  }
  loadingLoc.value = true
  try {
    const res = await getPublishDefaultLocation(cid)
    const loc = (res?.data || null) as Record<string, unknown> | null
    if (loc && (loc.divisionId || loc.city || loc.prov)) {
      const text = formatLoc(loc)
      if (applyAll || isBatch.value) {
        for (const d of drafts.value) {
          if (!d.location?.divisionId) {
            d.location = loc
            d.locationText = text
          }
        }
      }
      if (current.value) {
        current.value.location = loc
        current.value.locationText = text
      }
      if (!silent) message.success(text ? `已获取所在地：${text}` : '已获取所在地')
      persistDrafts()
    } else if (!silent) {
      message.warning('未获取到默认所在地，请确认账号 Cookie 有效')
    }
  } catch (e: any) {
    if (!silent) message.warning(e?.message || '获取所在地失败')
  } finally {
    loadingLoc.value = false
  }
}

function isOwnCdn(url: string): boolean {
  const u = (url || '').toLowerCase()
  return u.includes('stream-upload.goofish.com') || u.startsWith('data:')
}

async function transferDraftImages(draft: PublishDraft): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid || !draft.images.length) return
  for (const im of draft.images) {
    const src = im.url || im.localPreview || ''
    if (!src || isOwnCdn(src) || im.pending) continue
    // 已是自己上传过的 CDN
    if (src.includes('stream-upload.goofish.com')) continue
    im.pending = true
    try {
      const res = await transferPublishImage(cid, src)
      const info = res?.data
      if (info?.url) {
        im.localPreview = im.localPreview || src
        im.url = info.url
        im.width = info.width
        im.height = info.height
      }
    } catch {
      // 发布时后端还会再转存一次
    } finally {
      im.pending = false
    }
  }
  persistDrafts()
}

async function transferAllDraftImages(): Promise<void> {
  const list = drafts.value
  if (!list.length) return
  const need = list.some((d) =>
    d.images.some((im) => {
      const src = im.url || im.localPreview || ''
      return src.startsWith('http') && !src.includes('stream-upload.goofish.com')
    })
  )
  if (!need) return
  transferring.value = true
  transferTip.value = '正在把采集图片转存到闲鱼 CDN…'
  uploading.value = true
  try {
    for (const d of list) {
      await transferDraftImages(d)
    }
    transferTip.value = '图片转存完成，可直接发布'
  } catch {
    transferTip.value = '部分图片转存失败，发布时会再试一次'
  } finally {
    uploading.value = false
    transferring.value = false
  }
}

async function uploadDataUrl(dataUrl: string): Promise<void> {
  const cid = accountStore.activeCookieId
  const draft = current.value
  if (!cid) {
    message.warning('请先选择发布账号')
    return
  }
  if (!draft) return
  if (!canAddImage.value) {
    message.warning('最多 9 张商品图')
    return
  }
  // 先本地预览，再异步上传 CDN
  const placeholder: ImgItem = {
    url: dataUrl,
    localPreview: dataUrl,
    pending: true
  }
  draft.images.push(placeholder)
  uploading.value = true
  try {
    const res = await uploadPublishImageBase64(cid, dataUrl)
    const info = res?.data
    if (!info?.url) throw new Error('上传失败')
    placeholder.url = info.url
    placeholder.width = info.width
    placeholder.height = info.height
    placeholder.pending = false
    placeholder.localPreview = dataUrl
    message.success('图片已上传')
    persistDrafts()
  } catch (e: any) {
    const idx = draft.images.indexOf(placeholder)
    if (idx >= 0) draft.images.splice(idx, 1)
    message.error(e?.message || '图片上传失败')
  } finally {
    uploading.value = false
  }
}

const pasteGuardUntil = ref(0)

function handlePasteEvent(e: ClipboardEvent): void {
  // window + 输入框可能各触发一次，防重复
  const now = Date.now()
  if (now < pasteGuardUntil.value) {
    e.preventDefault()
    return
  }
  const items = e.clipboardData?.items
  if (!items) return
  for (const it of Array.from(items)) {
    if (it.type.startsWith('image/')) {
      e.preventDefault()
      pasteGuardUntil.value = now + 800
      const file = it.getAsFile()
      if (!file) return
      const reader = new FileReader()
      reader.onload = () => void uploadDataUrl(String(reader.result || ''))
      reader.readAsDataURL(file)
      return
    }
  }
}

function onPickFile(ev: Event): void {
  const input = ev.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  for (const file of files.slice(0, 9)) {
    if (!file.type.startsWith('image/')) continue
    const reader = new FileReader()
    reader.onload = () => void uploadDataUrl(String(reader.result || ''))
    reader.readAsDataURL(file)
  }
}

function removeImage(idx: number): void {
  current.value?.images.splice(idx, 1)
  persistDrafts()
}

function removeDraft(key: string): void {
  if (drafts.value.length <= 1) {
    clearForm()
    return
  }
  drafts.value = drafts.value.filter((d) => d.key !== key)
  if (activeKey.value === key) activeKey.value = drafts.value[0].key
  persistDrafts()
}

async function publishOne(draft: PublishDraft, scheduleAt: string | null): Promise<string | null> {
  const cid = accountStore.activeCookieId
  if (!cid) throw new Error('请先选择发布账号')
  const descText = draft.desc.trim()
  let titleText = draft.title.trim()
  if (!titleText && descText) {
    titleText = descText.split(/\r?\n/)[0].trim().slice(0, 30)
    draft.title = titleText
  }
  if (!descText && !titleText) throw new Error('请填写商品描述（标题可留空，将从描述自动生成）')
  if (!titleText) throw new Error('请填写商品描述以便生成标题')
  if (draft.price == null || Number(draft.price) <= 0) throw new Error('请填写有效售价')

  // 等上传中的图；外链再转存一次
  if (draft.images.some((im) => im.pending)) {
    throw new Error('图片仍在上传/转存中，请稍候再点发布')
  }
  await transferDraftImages(draft)

  const readyImgs = draft.images.filter((im) => im.url && !im.pending)
  if (!readyImgs.length) throw new Error('请至少添加 1 张商品图片')

  // 所在地：已有 divisionId 或用户手动填写时不再覆盖
  if (!draft.location?.divisionId && !draft.location?.manual) {
    await loadDefaultLocation(true, true)
  }

  // 类目：未选手动类目时先静默推荐一次
  if (!draft.category?.catId && !draft.category?.channelCatId) {
    activeKey.value = draft.key
    await loadRecommendCategory(true)
  }
  if (!draft.category?.catId && !draft.category?.channelCatId) {
    throw new Error(
      '未选择有效叶子类目。请点「推荐类目」后从下拉选择带 ID 的类目（不要只填「其他服务」等类目名，否则会报类目不存在）。'
    )
  }

  const res = await publishItem({
    cookie_id: cid,
    title: titleText,
    desc: descText || titleText,
    price: Number(draft.price),
    original_price: draft.originalPrice != null ? Number(draft.originalPrice) : 0,
    quantity: draft.quantity || 1,
    images: readyImgs.map((im) => ({
      url: im.url,
      width: im.width || 800,
      height: im.height || 600
    })),
    shipping: draft.shipping,
    post_price: draft.postPrice != null ? Number(draft.postPrice) : 0,
    can_self_pickup: draft.canSelfPickup,
    location: draft.location,
    category: draft.category,
    schedule_at: scheduleAt,
    dedup_text: !!draft.dedupText,
    crop_ratio: null
  })
  return (res as any)?.data?.item_id || null
}

async function maybeBindWatchAfterPublish(draft: PublishDraft, localItemId: string | null): Promise<void> {
  if (!localItemId || !draft.watchId || !draft.sourceId) return
  try {
    await bindWatchItem(draft.watchId, {
      source_item_id: draft.sourceId,
      local_item_id: localItemId,
      source_title: draft.title,
      last_source_price: draft.originalPrice != null ? String(draft.originalPrice) : '',
      dropship: draft.dropship ? 1 : 0
    })
    message.success(
      draft.dropship
        ? `已自动绑定监控并开启代发：本地 ${localItemId}`
        : `已自动绑定监控：本地 ${localItemId}`
    )
  } catch (e: any) {
    message.warning(e?.message || '发布成功，但自动绑定监控失败，请到卖家监控手动绑定')
  }
}

async function publishBatchAll(scheduleAt: string | null): Promise<void> {
  const gap = Math.max(5, Math.min(300, Number(intervalSec.value) || 30))
  let ok = 0
  for (let i = 0; i < drafts.value.length; i++) {
    const d = drafts.value[i]
    activeKey.value = d.key
    batchProgress.value = `正在发布 ${i + 1}/${drafts.value.length}：${d.label}`
    try {
      const itemId = await publishOne(d, i === 0 ? scheduleAt : null)
      await maybeBindWatchAfterPublish(d, itemId)
      ok += 1
      message.success(itemId ? `${d.label} 发布成功：${itemId}` : `${d.label} 发布成功`)
    } catch (e: any) {
      message.error(`${d.label}：${e?.message || '发布失败'}`)
    }
    if (i < drafts.value.length - 1) {
      batchProgress.value = `已完成 ${i + 1}/${drafts.value.length}，${gap} 秒后发下一件…`
      await new Promise((r) => setTimeout(r, gap * 1000))
    }
  }
  batchProgress.value = `批量完成：成功 ${ok}/${drafts.value.length}`
  if (ok === drafts.value.length) {
    sessionStorage.removeItem('xy_publish_draft')
    sessionStorage.removeItem('xy_publish_drafts')
    clearForm()
  } else {
    persistDrafts()
  }
}

async function onPublish(mode: 'current' | 'all' = 'current'): Promise<void> {
  if (!current.value) return
  let scheduleAt: string | null = null
  if (current.value.scheduleEnabled && current.value.scheduleTime) {
    scheduleAt = new Date(current.value.scheduleTime).toISOString()
  }
  publishing.value = true
  batchProgress.value = ''
  try {
    const doAll = mode === 'all' || (isBatch.value && intervalEnabled.value)
    if (doAll && isBatch.value) {
      await publishBatchAll(scheduleAt)
    } else {
      const itemId = await publishOne(current.value, scheduleAt)
      await maybeBindWatchAfterPublish(current.value, itemId)
      message.success(
        itemId
          ? `发布成功，商品ID：${itemId}。可在「商品管理」查看`
          : '发布成功，可在「商品管理」查看'
      )
      if (!isBatch.value) {
        sessionStorage.removeItem('xy_publish_draft')
        sessionStorage.removeItem('xy_publish_drafts')
        clearForm()
      } else {
        removeDraft(current.value.key)
      }
    }
  } catch (e: any) {
    message.error(e?.message || '发布失败')
  } finally {
    publishing.value = false
  }
}

watch(
  drafts,
  () => {
    persistDrafts()
  },
  { deep: true }
)

onMounted(() => {
  loadDrafts()
  // 从卖家监控「编辑上架」带过来的草稿：若标记了去重，进入页面即生效
  for (const d of drafts.value) {
    if (d.dedupText) {
      d.originTitle = d.originTitle || d.title
      d.originDesc = d.originDesc || d.desc
      applyDedupToDraft(d, true)
    }
  }
  void loadDefaultLocation(true, true)
  void transferAllDraftImages()
  window.addEventListener('paste', handlePasteEvent)
})

onUnmounted(() => {
  window.removeEventListener('paste', handlePasteEvent)
})
</script>

<template>
  <n-card size="small" :bordered="false" style="background: transparent">
    <AccountTabs :show-unread="false" @change="() => loadDefaultLocation(true, true)" />
    <n-text depth="3" style="display: block; margin: 8px 0 12px; font-size: 12px">
      在软件内直接发布到闲鱼（非打开网页）。商品图最多 9 张（3×3），第一张为主图；支持 Ctrl+V
      粘贴。采集图会自动转存 CDN。
    </n-text>

    <n-tabs
      v-if="drafts.length"
      v-model:value="activeKey"
      type="card"
      size="small"
      style="margin-bottom: 12px"
      @close="removeDraft"
    >
      <n-tab-pane
        v-for="d in drafts"
        :key="d.key"
        :name="d.key"
        :tab="d.label"
        :closable="drafts.length > 1"
      />
    </n-tabs>

    <template v-if="current">
      <n-form label-placement="left" label-width="100" style="max-width: 780px">
        <n-form-item label="商品图片" required>
          <div class="img-box" tabindex="0">
            <div v-for="(im, idx) in current.images" :key="(im.localPreview || im.url) + idx" class="img-item">
              <n-image
                :src="im.localPreview || im.url"
                width="88"
                height="88"
                object-fit="cover"
                fallback-src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='88' height='88'%3E%3Crect fill='%23eee' width='88' height='88'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' fill='%23999' font-size='12'%3E图%3C/text%3E%3C/svg%3E"
              />
              <n-button size="tiny" type="error" secondary class="rm" @click="removeImage(idx)"
                >移除</n-button
              >
              <n-text v-if="idx === 0" depth="3" style="font-size: 11px">主图</n-text>
              <n-text v-else-if="im.pending" depth="3" style="font-size: 11px">上传中…</n-text>
            </div>
            <div v-if="canAddImage" class="img-add">
              <input
                ref="fileInput"
                type="file"
                accept="image/*"
                multiple
                hidden
                @change="onPickFile"
              />
              <n-button size="small" :loading="uploading" @click="fileInput?.click()"
                >上传图片</n-button
              >
              <n-text depth="3" style="font-size: 11px; margin-top: 4px">或 Ctrl+V 粘贴</n-text>
            </div>
          </div>
        </n-form-item>

        <n-form-item label="标题">
          <n-input
            v-model:value="current.title"
            maxlength="30"
            show-count
            placeholder="可不填，发布时自动取描述首行（最多30字）"
          />
        </n-form-item>
        <n-form-item label="描述" required>
          <n-input
            v-model:value="current.desc"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 8 }"
            placeholder="商品描述（必填；标题留空时用首行生成）"
          />
        </n-form-item>
        <n-form-item label="售价" required>
          <n-input-number v-model:value="current.price" :min="0.01" :precision="2" style="width: 200px" />
        </n-form-item>
        <n-form-item label="原价">
          <n-input-number
            v-model:value="current.originalPrice"
            :min="0"
            :precision="2"
            style="width: 200px"
            clearable
          />
        </n-form-item>
        <n-form-item label="库存数量">
          <n-input-number v-model:value="current.quantity" :min="1" :max="9999" style="width: 200px" />
        </n-form-item>
        <n-form-item label="商品类目">
          <n-space align="start" vertical style="width: 100%">
            <n-space align="center">
              <n-select
                v-model:value="selectedCategoryValue"
                :options="categorySelectOptions"
                clearable
                filterable
                placeholder="先点右侧推荐，或发布时自动推荐"
                style="width: 360px"
              />
              <n-button
                size="small"
                type="primary"
                secondary
                :loading="loadingCat"
                @click="loadRecommendCategory(false)"
              >
                智能推荐类目
              </n-button>
            </n-space>
            <n-text depth="3" style="font-size: 12px">
              与闲鱼网页发布一致，根据标题和图片推荐类目；也可在下拉框里手动切换
            </n-text>
          </n-space>
        </n-form-item>
        <n-form-item label="运费方式">
          <n-select v-model:value="current.shipping" :options="shippingOptions" style="width: 220px" />
        </n-form-item>
        <n-form-item v-if="current.shipping === 'fixed'" label="运费金额">
          <n-input-number v-model:value="current.postPrice" :min="0" :precision="2" style="width: 200px" />
        </n-form-item>
        <n-form-item label="自提">
          <n-checkbox v-model:checked="current.canSelfPickup">支持当面交易/自提</n-checkbox>
        </n-form-item>
        <n-form-item label="宝贝所在地">
          <n-space align="center">
            <n-input
              :value="current.locationText"
              placeholder="例：广东省深圳市南山区；或点右侧获取账号默认位置"
              style="width: 360px"
              @update:value="onLocationTextInput"
            />
            <n-button size="small" type="primary" secondary :loading="loadingLoc" @click="loadDefaultLocation(false)"
              >获取账号默认位置</n-button
            >
          </n-space>
          <n-text depth="3" style="display: block; margin-top: 4px; font-size: 12px">
            推荐点「获取账号默认位置」（带完整区划 ID，发布最稳）。也可手动填省市区文字；手动填写会随商品提交，系统不再强行覆盖。
          </n-text>
        </n-form-item>
        <n-form-item label="定时发布">
          <n-space align="center">
            <n-checkbox v-model:checked="current.scheduleEnabled">启用（1 小时内）</n-checkbox>
            <n-date-picker
              v-if="current.scheduleEnabled"
              v-model:value="current.scheduleTime"
              type="datetime"
              clearable
            />
          </n-space>
        </n-form-item>
        <n-form-item label="自动去重">
          <n-space align="center">
            <n-checkbox
              :checked="current.dedupText"
              @update:checked="onDedupToggle"
            >
              启用（仅改写文案，图片保持原图）
            </n-checkbox>
            <n-tooltip trigger="hover" style="max-width: 320px">
              <template #trigger>
                <n-button text type="info" style="padding: 0 4px; font-size: 14px">?</n-button>
              </template>
              适合从淘宝/京东等渠道复制来的商品：勾选后会重组标题结构、批量同义替换、重写描述段落；
              取消勾选会恢复原文。图片一律上传原图，不做裁剪/模糊处理。
            </n-tooltip>
          </n-space>
        </n-form-item>
        <n-form-item v-if="isBatch" label="批量间隔">
          <n-space align="center">
            <n-checkbox v-model:checked="intervalEnabled">按间隔依次发布全部标签</n-checkbox>
            <n-input-number
              v-if="intervalEnabled"
              v-model:value="intervalSec"
              :min="5"
              :max="300"
              style="width: 120px"
            />
            <n-text v-if="intervalEnabled" depth="3">秒</n-text>
          </n-space>
        </n-form-item>
        <n-form-item v-if="current.sourceUrl" label="来源">
          <n-text depth="3" style="font-size: 12px; word-break: break-all">{{ current.sourceUrl }}</n-text>
        </n-form-item>
      </n-form>

      <n-text v-if="transferTip || transferring" depth="3" style="display: block; margin: 0 0 8px; font-size: 12px">
        {{ transferTip || '图片处理中…' }}
      </n-text>

      <n-text v-if="batchProgress" depth="3" style="display: block; margin: 8px 0; font-size: 12px">
        {{ batchProgress }}
      </n-text>

      <n-space style="margin-top: 8px">
        <n-button secondary :disabled="publishing || transferring || uploading" @click="runAutoDedupOnce">
          自动去重
        </n-button>
        <n-button
          type="primary"
          :loading="publishing"
          :disabled="transferring || uploading"
          @click="onPublish(isBatch && intervalEnabled ? 'all' : 'current')"
        >
          {{
            isBatch && intervalEnabled
              ? `间隔发布全部（${drafts.length}，每 ${intervalSec} 秒）`
              : '发布到闲鱼'
          }}
        </n-button>
        <n-button
          v-if="isBatch"
          type="primary"
          secondary
          :loading="publishing"
          :disabled="transferring || uploading"
          @click="onPublish('current')"
          >仅发布当前标签</n-button
        >
        <n-button
          v-if="isBatch && !intervalEnabled"
          secondary
          :loading="publishing"
          :disabled="transferring || uploading"
          @click="onPublish('all')"
          >按间隔发布全部</n-button
        >
        <n-button secondary @click="clearForm">一键清空</n-button>
        <n-button quaternary @click="router.push({ name: 'collect' })">返回采集</n-button>
      </n-space>
    </template>
    <template v-else>
      <n-space vertical :size="12" style="padding: 24px 0">
        <n-text depth="3">当前没有可编辑的草稿。</n-text>
        <n-button type="primary" @click="ensureDraft">新建空白商品</n-button>
      </n-space>
    </template>
  </n-card>
</template>

<style scoped>
.publish-card {
  background: transparent;
}
.img-box {
  display: grid;
  grid-template-columns: repeat(3, 96px);
  gap: 10px;
  align-items: start;
  outline: none;
  max-width: 320px;
}
.img-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 96px;
}
.img-add {
  width: 96px;
  min-height: 96px;
  border: 1px dashed var(--app-border, #ccc);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px;
  box-sizing: border-box;
}
.rm {
  margin-top: 2px;
}
</style>
