<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NAlert,
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
  NSpace,
  NSpin,
  NTag,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns,
  type DropdownOption
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  deleteItem,
  editItem,
  getItemEditDetail,
  getItems,
  polishItem,
  syncItemsFromAccount,
  updateItemLocalStatus,
  batchUpdateItemPrice,
  type ItemRow
} from '../api/items'

const message = useMessage()
const dialog = useDialog()
const accountStore = useAccountStore()
const loading = ref(false)
const syncing = ref(false)
const allRows = ref<ItemRow[]>([])
const checked = ref<Array<string | number>>([])
const page = ref(1)
const pageSize = ref(20)
const pageSizeOptions = [20, 50, 100]
const polishedIds = ref<Set<string>>(new Set())
const autoSyncHint = ref('')
let autoSyncTimer: ReturnType<typeof setInterval> | null = null

const showEditModal = ref(false)
const editSaving = ref(false)
const editLoading = ref(false)
const editTarget = ref<ItemRow | null>(null)
const editForm = ref({
  title: '',
  desc: '',
  price: null as number | null,
  original_price: null as number | null,
  images: [] as string[],
  tip: '',
  appOnly: false
})

const AUTO_SYNC_MS = 15 * 60 * 1000
let _reloadGen = 0

function polishKey(cookieId: string): string {
  return `xy_polished_${cookieId || 'default'}`
}

function loadPolished(cookieId: string): void {
  try {
    const arr = JSON.parse(localStorage.getItem(polishKey(cookieId)) || '[]')
    polishedIds.value = new Set(Array.isArray(arr) ? arr.map(String) : [])
  } catch {
    polishedIds.value = new Set()
  }
}

function savePolished(cookieId: string): void {
  localStorage.setItem(polishKey(cookieId), JSON.stringify([...polishedIds.value]))
}

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return allRows.value.slice(start, start + pageSize.value)
})

function openItem(row: ItemRow): void {
  const id = row.item_id || row.id
  if (!id) return
  window.open(`https://www.goofish.com/item?id=${id}`, '_blank')
}

function rowKey(r: ItemRow): string {
  return String(r.item_id || r.id || '')
}

function metricVal(r: ItemRow, ...keys: string[]): string | number {
  for (const k of keys) {
    const v = (r as any)[k]
    if (v !== undefined && v !== null && v !== '' && v !== '-') return v as string | number
  }
  return '-'
}

function opOptions(r: ItemRow): DropdownOption[] {
  const off = r.local_status === 'off'
  const polished = polishedIds.value.has(rowKey(r))
  return [
    { label: '打开商品', key: 'open' },
    { label: '编辑', key: 'edit' },
    { label: off ? '上架' : '下架', key: 'toggle' },
    { label: polished ? '已擦亮（无法取消）' : '擦亮', key: 'polish', disabled: polished },
    { label: '删除（闲鱼+本地）', key: 'delete' }
  ]
}

async function openEdit(r: ItemRow): Promise<void> {
  editTarget.value = r
  const cookieId = String(r.cookie_id || accountStore.activeCookieId || '')
  const itemId = rowKey(r)
  const priceRaw = r.price ?? r.item_price
  const origRaw = r.original_price
  let price: number | null = null
  let original_price: number | null = null
  try {
    const p = Number(String(priceRaw ?? '').replace(/[￥¥,\s]/g, ''))
    if (Number.isFinite(p) && p > 0) price = p
  } catch {
    /* ignore */
  }
  try {
    const o = Number(String(origRaw ?? '').replace(/[￥¥,\s]/g, ''))
    if (Number.isFinite(o) && o > 0) original_price = o
  } catch {
    /* ignore */
  }
  editForm.value = {
    title: String(r.title || r.item_title || ''),
    desc: String((r as any).desc || (r as any).item_description || (r as any).description || ''),
    price,
    original_price,
    images: String(r.item_pic || r.pic_url || '') ? [String(r.item_pic || r.pic_url)] : [],
    tip: '',
    appOnly: false
  }
  showEditModal.value = true
  if (!cookieId || !itemId) return
  editLoading.value = true
  try {
    const res = await getItemEditDetail(cookieId, itemId)
    const d = res?.data
    if (!d) return
    editForm.value = {
      title: String(d.title || editForm.value.title || ''),
      desc: String(d.desc ?? editForm.value.desc ?? ''),
      price: d.price != null && Number(d.price) > 0 ? Number(d.price) : editForm.value.price,
      original_price:
        d.original_price != null && Number(d.original_price) > 0
          ? Number(d.original_price)
          : editForm.value.original_price,
      images: Array.isArray(d.images) && d.images.length ? d.images.map(String) : editForm.value.images,
      tip: String(d.tip || ''),
      appOnly: !!d.app_only
    }
    if (d.app_only) {
      message.warning(d.tip || '该商品可能仅支持闲鱼 App 编辑')
    } else if (d.tip && !(d.desc || d.title)) {
      message.warning(d.tip)
    }
  } catch (e: any) {
    editForm.value.tip = e?.message || '拉取编辑详情失败，已用列表信息预填'
    message.warning(editForm.value.tip)
  } finally {
    editLoading.value = false
  }
}

async function saveEdit(): Promise<void> {
  const r = editTarget.value
  const cookieId = String(r?.cookie_id || accountStore.activeCookieId || '')
  const itemId = r ? rowKey(r) : ''
  if (!cookieId || !itemId) {
    message.warning('缺少账号或商品')
    return
  }
  const title = editForm.value.title.trim()
  const desc = editForm.value.desc.trim()
  const price = editForm.value.price
  const original_price = editForm.value.original_price
  if (!title && !desc && (price == null || !(price > 0)) && (original_price == null || !(original_price > 0))) {
    message.warning('请至少填写一项')
    return
  }
  editSaving.value = true
  try {
    const payload: Parameters<typeof editItem>[0] = {
      cookie_id: cookieId,
      item_id: itemId
    }
    if (title) payload.title = title
    // 本地常无描述缓存：空字符串不提交，避免误清空闲鱼端描述
    if (desc) payload.desc = desc
    if (price != null && price > 0) payload.price = price
    if (original_price != null && original_price > 0) payload.original_price = original_price
    const res = await editItem(payload)
    message.success(res?.message || '已保存')
    showEditModal.value = false
    await reloadLocal()
  } catch (e: any) {
    message.error(e?.message || '编辑失败')
  } finally {
    editSaving.value = false
  }
}

async function onOp(key: string | number, r: ItemRow): Promise<void> {
  const cookieId = String(r.cookie_id || accountStore.activeCookieId)
  const itemId = rowKey(r)
  if (key === 'open') openItem(r)
  else if (key === 'edit') void openEdit(r)
  else if (key === 'toggle') await toggleStatus(cookieId, itemId, r)
  else if (key === 'polish') {
    if (polishedIds.value.has(itemId)) {
      message.warning('已擦亮的商品无法取消擦亮（平台不支持）')
      return
    }
    await onPolish(cookieId, itemId)
  } else if (key === 'delete') onDelete(cookieId, itemId)
}

const columns: DataTableColumns<ItemRow> = [
  { type: 'selection', width: 48 },
  {
    title: '图',
    key: 'pic',
    width: 64,
    render: (r) =>
      h(NImage, {
        src: String(r.item_pic || r.pic_url || ''),
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
          href: 'javascript:;',
          style: 'color: var(--n-primary-color)',
          onClick: (e: Event) => {
            e.preventDefault()
            openItem(r)
          }
        },
        String(r.title || r.item_title || '-')
      )
  },
  {
    title: '现价',
    key: 'price',
    width: 90,
    render: (r) =>
      h('span', { style: 'color:#18a058' }, String(r.price ?? r.item_price ?? '-'))
  },
  {
    title: '原价',
    key: 'original_price',
    width: 90,
    render: (r) =>
      h(
        'span',
        { style: 'color:#f0a020; text-decoration: line-through' },
        String(r.original_price ?? '-')
      )
  },
  {
    title: '分类',
    key: 'item_category',
    width: 100,
    ellipsis: { tooltip: true },
    render: (r) => r.item_category || r.category || '-'
  },
  {
    title: '曝光',
    key: 'exposure_count',
    width: 70,
    render: (r) => {
      const v = metricVal(r, 'exposure_count', 'exposure', 'exposeCnt')
      const view = metricVal(r, 'view_count', 'browseCnt', 'browse_count')
      if ((v === '-' || v === '' || v == null) && view !== '-') {
        return h('span', { title: '列表接口无真实曝光，暂用浏览量近似' }, `${view}≈`)
      }
      return v
    }
  },
  {
    title: '浏览',
    key: 'view_count',
    width: 70,
    render: (r) => metricVal(r, 'view_count', 'browseCnt', 'browse_count')
  },
  {
    title: '想要',
    key: 'want_num',
    width: 70,
    render: (r) => metricVal(r, 'want_num', 'want_count', 'wantCnt')
  },
  {
    title: '状态',
    key: 'local_status',
    width: 120,
    render: (r) =>
      h(NSpace, { size: 4 }, () => [
        h(NTag, { size: 'small', type: r.local_status === 'off' ? 'warning' : 'success' }, () =>
          r.local_status === 'off' ? '下架' : '上架'
        ),
        polishedIds.value.has(rowKey(r))
          ? h(NTag, { size: 'small', type: 'info' }, () => '已擦亮')
          : null
      ])
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render: (r) =>
      h(
        NDropdown,
        { trigger: 'click', options: opOptions(r), onSelect: (k: string | number) => void onOp(k, r) },
        () => h(NButton, { size: 'tiny' }, () => '操作')
      )
  }
]

async function load(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    allRows.value = []
    return
  }
  loadPolished(cookieId)
  loading.value = true
  try {
    allRows.value = await getItems(cookieId)
    page.value = 1
    checked.value = []
  } catch (e: any) {
    message.error(e?.message || '加载商品失败')
  } finally {
    loading.value = false
  }
}

/** 仅刷新本地库列表，不触发闲鱼全量拉取（快） */
async function reloadLocal(): Promise<void> {
  if (syncing.value) return
  const gen = ++_reloadGen
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    allRows.value = []
    return
  }
  loadPolished(cookieId)
  loading.value = true
  try {
    const rows = await getItems(cookieId)
    if (gen !== _reloadGen) return
    allRows.value = rows
    page.value = 1
    checked.value = []
  } catch (e: any) {
    if (gen === _reloadGen) message.error(e?.message || '加载商品失败')
  } finally {
    if (gen === _reloadGen) loading.value = false
  }
}

async function onSync(silent = false): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId || syncing.value) return
  syncing.value = true
  autoSyncHint.value = silent ? '后台静默同步中…' : '正在快速同步最新列表…'
  // 同步过程中每 2 秒刷新本地列表，避免干等白屏
  const poll = setInterval(() => {
    void reloadLocalQuiet()
  }, 2000)
  try {
    const res: any = await syncItemsFromAccount(cookieId, {
      fast: true,
      page_size: 50,
      page_delay: 0.15,
      skip_detail: true
    })
    autoSyncHint.value = `上次同步 ${new Date().toLocaleTimeString()} · ${res?.total_count ?? ''} 件`
    if (!silent) message.success(res?.message || '已同步最新商品列表')
    await reloadLocal()
  } catch (e: any) {
    if (!silent) message.error(e?.message || '同步失败')
    else autoSyncHint.value = `自动同步失败：${e?.message || '请稍后重试'}`
  } finally {
    clearInterval(poll)
    syncing.value = false
  }
}

async function reloadLocalQuiet(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId || loading.value) return
  try {
    const rows = await getItems(cookieId)
    allRows.value = rows
  } catch {
    /* ignore */
  }
}

async function toggleStatus(cookieId: string, itemId: string, row: ItemRow): Promise<void> {
  const next = row.local_status === 'off' ? 'on' : 'off'
  try {
    const res = await updateItemLocalStatus(cookieId, itemId, next)
    const ok = (res as any)?.success !== false
    const msg = String((res as any)?.message || '')
    if (!ok) {
      message.error(msg || (next === 'on' ? '上架失败' : '下架失败'))
      return
    }
    message.success(msg || (next === 'on' ? '已上架' : '已下架'))
    row.local_status = next
    await load()
  } catch (e: any) {
    message.error(e?.message || '操作失败')
  }
}

async function onPolish(cookieId: string, itemId: string): Promise<void> {
  try {
    await polishItem(cookieId, itemId)
    polishedIds.value.add(itemId)
    polishedIds.value = new Set(polishedIds.value)
    savePolished(cookieId)
    message.success('商品已擦亮')
  } catch (e: any) {
    message.error(e?.message || '擦亮失败')
  }
}

function onDelete(cookieId: string, itemId: string): void {
  dialog.warning({
    title: '确认删除',
    content:
      '将调用闲鱼删除接口从手机端移除该商品，并删除本地记录。若平台删除失败会自动尝试下架。确定继续？',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await deleteItem(cookieId, itemId)
        message.success((res as any)?.message || '已删除')
        await load()
      } catch (e: any) {
        message.error(e?.message || '删除失败')
      }
    }
  })
}

async function onBatchDelete(): Promise<void> {
  if (!checked.value.length) return
  dialog.warning({
    title: '批量删除',
    content: `将删除已选 ${checked.value.length} 件商品（闲鱼端 + 本地）。确定？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      const cid = accountStore.activeCookieId
      if (!cid) return
      let ok = 0
      for (const id of checked.value) {
        try {
          await deleteItem(cid, String(id))
          ok += 1
        } catch {
          /* continue */
        }
      }
      message.success(`已删除 ${ok}/${checked.value.length} 件`)
      checked.value = []
      await load()
    }
  })
}

async function onBatchPrice(): Promise<void> {
  if (!checked.value.length) {
    message.warning('请先勾选商品')
    return
  }
  const cid = accountStore.activeCookieId
  if (!cid) return
  const mode = window.prompt('改价模式：输入 set=统一设价，markup=按现价加价', 'set')
  if (!mode) return
  if (mode === 'set') {
    const p = window.prompt('统一设为多少元？', '')
    if (!p) return
    const price = Number(p)
    if (!(price > 0)) {
      message.warning('价格无效')
      return
    }
    const items = checked.value.map((id) => ({ cookie_id: cid, item_id: String(id), price }))
    const res = await batchUpdateItemPrice({ items })
    message.success(res.message || '批量改价完成')
  } else {
    const t = window.prompt('加价类型 percent=比例(%) / amount=金额(元)', 'percent')
    const v = window.prompt('加价值（如 1 表示 1% 或 +1 元）', '1')
    if (!t || !v) return
    const res = await batchUpdateItemPrice({
      cookie_id: cid,
      item_ids: checked.value.map(String),
      mode: 'markup',
      markup_type: t === 'amount' ? 'amount' : 'percent',
      markup_value: Number(v)
    })
    message.success(res.message || '批量改价完成')
  }
  await load()
}

async function onBatchPolish(): Promise<void> {
  if (!checked.value.length) {
    message.warning('请先勾选商品')
    return
  }
  const cid = accountStore.activeCookieId
  if (!cid) return
  let ok = 0
  let skip = 0
  message.loading(`正在擦亮 ${checked.value.length} 件…`, { duration: 0 })
  try {
    for (const id of checked.value) {
      const itemId = String(id)
      if (polishedIds.value.has(itemId)) {
        skip += 1
        continue
      }
      try {
        await polishItem(cid, itemId)
        polishedIds.value.add(itemId)
        ok += 1
        await new Promise((r) => setTimeout(r, 800))
      } catch {
        /* continue */
      }
    }
    polishedIds.value = new Set(polishedIds.value)
    savePolished(cid)
    message.success(`擦亮完成：成功 ${ok}，已擦过跳过 ${skip}`)
  } finally {
    message.destroyAll()
  }
}

watch(
  () => accountStore.activeCookieId,
  () => {
    void reloadLocal()
  }
)

function onPageChange(p: number): void {
  page.value = p
}

function onPageSizeChange(ps: number): void {
  pageSize.value = ps
  page.value = 1
}

onMounted(() => {
  // 进入页面：先秒开本地列表；全量同步改由用户点「从账号同步」
  void reloadLocal()
  autoSyncHint.value = '列表来自本地缓存；需要最新数据请点「从账号同步」'
  // 后台低频同步：15 分钟一次，且页面可见时才跑
  autoSyncTimer = setInterval(() => {
    if (document.visibilityState === 'hidden') return
    if (syncing.value || loading.value) return
    void onSync(true)
  }, AUTO_SYNC_MS)
})

onUnmounted(() => {
  if (autoSyncTimer) {
    clearInterval(autoSyncTimer)
    autoSyncTimer = null
  }
})
</script>

<template>
  <n-card title="商品管理" size="small">
    <AccountTabs :show-unread="false" />
    <n-space style="margin-bottom: 12px" align="center">
      <n-button type="primary" :loading="syncing" @click="onSync(false)">从账号同步</n-button>
      <n-button secondary :disabled="!checked.length" @click="onBatchPrice">批量改价</n-button>
      <n-button secondary :disabled="!checked.length" @click="onBatchPolish">批量擦亮</n-button>
      <n-button type="error" secondary :disabled="!checked.length" @click="onBatchDelete">
        删除已选
      </n-button>
      <n-tag v-if="checked.length" type="info" size="small">当前已选 {{ checked.length }} 条</n-tag>
      <n-text depth="3">共 {{ allRows.length }} 条</n-text>
      <n-text depth="3" style="font-size: 12px">
        进入秒开本地列表 · 后台约 15 分钟静默同步一次
        <template v-if="autoSyncHint"> · {{ autoSyncHint }}</template>
      </n-text>
    </n-space>
    <n-data-table
      v-model:checked-row-keys="checked"
      :loading="loading || syncing"
      :columns="columns"
      :data="pagedRows"
      size="small"
      :bordered="false"
      :row-key="rowKey"
      :scroll-x="1200"
      flex-height
      style="height: calc(100vh - 280px)"
    />
    <n-space v-if="allRows.length" justify="end" style="margin-top: 12px">
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="allRows.length"
        :page-sizes="pageSizeOptions"
        show-size-picker
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </n-space>
    <n-empty
      v-if="!loading && !allRows.length"
      description="暂无商品，进入页面将自动从账号同步"
      style="margin-top: 24px"
    />

    <n-modal
      v-model:show="showEditModal"
      preset="card"
      title="编辑商品"
      style="width: 560px"
      :mask-closable="!editSaving && !editLoading"
    >
      <n-spin :show="editLoading">
        <n-alert
          v-if="editForm.tip"
          :type="editForm.appOnly ? 'warning' : 'info'"
          style="margin-bottom: 12px"
          :bordered="false"
        >
          {{ editForm.tip }}
        </n-alert>
        <n-form label-placement="left" label-width="72">
          <n-form-item v-if="editForm.images.length" label="图片">
            <n-space>
              <n-image
                v-for="(src, idx) in editForm.images.slice(0, 8)"
                :key="idx + src"
                :src="src"
                width="56"
                height="56"
                object-fit="cover"
                style="border-radius: 4px"
              />
            </n-space>
          </n-form-item>
          <n-form-item label="标题">
            <n-input v-model:value="editForm.title" placeholder="商品标题" maxlength="60" show-count />
          </n-form-item>
          <n-form-item label="描述">
            <n-input
              v-model:value="editForm.desc"
              type="textarea"
              placeholder="正在从闲鱼拉取描述…"
              :autosize="{ minRows: 3, maxRows: 8 }"
            />
          </n-form-item>
          <n-form-item label="现价">
            <n-input-number
              v-model:value="editForm.price"
              :min="0.01"
              :precision="2"
              placeholder="元"
              style="width: 100%"
            />
          </n-form-item>
          <n-form-item label="原价">
            <n-input-number
              v-model:value="editForm.original_price"
              :min="0.01"
              :precision="2"
              placeholder="可选"
              style="width: 100%"
            />
          </n-form-item>
        </n-form>
      </n-spin>
      <n-space justify="end" style="margin-top: 8px">
        <n-button :disabled="editSaving || editLoading" @click="showEditModal = false">取消</n-button>
        <n-button type="primary" :loading="editSaving" :disabled="editLoading" @click="saveEdit"
          >保存</n-button
        >
      </n-space>
    </n-modal>
  </n-card>
</template>
