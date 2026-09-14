<script setup lang="ts">
import { h, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NDropdown,
  NImage,
  NPagination,
  NSelect,
  NSpace,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns,
  type DropdownOption
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  deleteOrder,
  getOrderDetail,
  getOrders,
  manualShipOrder,
  pullOrders,
  refreshSingleOrder,
  syncOrders,
  adjustOrderPrice,
  type OrderRow
} from '../api/orders'

const message = useMessage()
const dialog = useDialog()
const accountStore = useAccountStore()
const loading = ref(false)
const syncing = ref(false)
const fillingReceiver = ref(false)
const rows = ref<OrderRow[]>([])
const total = ref(0)
const status = ref('all')
const page = ref(1)
const pageSize = ref(20)
const hint = ref('')
const checked = ref<Array<string | number>>([])
const detailShow = ref(false)
const detailJson = ref('')

const pageSizeOptions = [20, 50, 100]

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待发货', value: 'pending_ship' },
  { label: '已发货', value: 'shipped' },
  { label: '已完成', value: 'completed' },
  { label: '退款中', value: 'refunding' },
  { label: '已取消', value: 'cancelled' }
]

const statusLabelMap: Record<string, string> = {
  pending_ship: '待发货',
  pending: '待付款',
  shipped: '已发货',
  completed: '已完成',
  refunding: '退款中',
  cancelled: '已取消',
  closed: '已关闭',
  unknown: '未知'
}

function statusLabel(s?: string): string {
  const key = String(s || '')
  return statusLabelMap[key] || key || '-'
}

function rowKey(r: OrderRow): string {
  return String(r.order_id || r.id || '')
}

function dash(v: unknown): string {
  const s = String(v ?? '').trim()
  return s || '-'
}

function opOptions(_r: OrderRow): DropdownOption[] {
  return [
    { label: '详情', key: 'detail' },
    { label: '同步单条', key: 'refresh' },
    { label: '未付款改价', key: 'adjust_price' },
    { label: '发货', key: 'ship' },
    { label: '查看订单号/退款', key: 'order_page' },
    { label: '评价 / 小红花', key: 'review' },
    { label: '再次购买', key: 'rebuy' },
    { label: '删除', key: 'delete' }
  ]
}

async function onOp(key: string | number, r: OrderRow): Promise<void> {
  const oid = rowKey(r)
  if (key === 'detail') {
    try {
      const d = await getOrderDetail(oid)
      detailJson.value = JSON.stringify(d || r, null, 2)
      detailShow.value = true
    } catch {
      detailJson.value = JSON.stringify(r, null, 2)
      detailShow.value = true
    }
  } else if (key === 'refresh') {
    try {
      await refreshSingleOrder(oid)
      message.success('已同步该订单')
      await load()
    } catch (e: any) {
      message.error(e?.message || '同步失败')
    }
  } else if (key === 'ship') {
    try {
      await manualShipOrder([oid], 'manual')
      message.success('已提交发货')
      await load()
    } catch (e: any) {
      message.error(e?.message || '发货失败')
    }
  } else if (key === 'adjust_price') {
    const p = window.prompt('待付款订单改价为多少元？', String(r.price || ''))
    if (!p) return
    const price = Number(p)
    if (!(price > 0)) {
      message.warning('价格无效')
      return
    }
    try {
      await adjustOrderPrice(oid, String(r.cookie_id || accountStore.activeCookieId || ''), price)
      message.success('改价已提交')
      await load()
    } catch (e: any) {
      message.error(e?.message || '改价失败（接口可能需抓包校准）')
    }
  } else if (key === 'delete') {
    dialog.warning({
      title: '确认删除',
      content: `确定删除订单 ${oid} 吗？`,
      positiveText: '删除',
      negativeText: '取消',
      onPositiveClick: async () => {
        await deleteOrder(oid)
        message.success('已删除')
        await load()
      }
    })
  } else if (key === 'order_page') {
    window.open(
      `https://www.goofish.com/order-detail?orderId=${encodeURIComponent(oid)}`,
      '_blank'
    )
  } else if (key === 'review') {
    window.open(
      `https://www.goofish.com/order-detail?orderId=${encodeURIComponent(oid)}`,
      '_blank'
    )
  } else if (key === 'rebuy') {
    const itemId = String(r.item_id || '')
    if (itemId) window.open(`https://www.goofish.com/item?id=${itemId}`, '_blank')
    else
      window.open(
        `https://www.goofish.com/order-detail?orderId=${encodeURIComponent(oid)}`,
        '_blank'
      )
  }
}

const columns: DataTableColumns<OrderRow> = [
  { type: 'selection', width: 48 },
  {
    title: '序号',
    key: 'idx',
    width: 56,
    render: (_r, i) => i + 1 + (page.value - 1) * pageSize.value
  },
  {
    title: '缩略图',
    key: 'thumb',
    width: 72,
    render: (r) => {
      const src = String(r.item_pic || r.pic_url || r.item_image || '')
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
    title: '订单号',
    key: 'order_id',
    width: 140,
    ellipsis: { tooltip: true },
    render: (r) => r.order_id || r.id || '-'
  },
  {
    title: '商品',
    key: 'item_title',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render: (r) => r.item_title || '-'
  },
  {
    title: '买家',
    key: 'buyer_nick',
    width: 110,
    ellipsis: { tooltip: true },
    render: (r) => r.buyer_nick || r.buyer_name || r.buyer_id || '-'
  },
  {
    title: '金额',
    key: 'amount',
    width: 90,
    render: (r) =>
      h('span', { style: 'color:#d03050;font-weight:600' }, String(r.amount ?? r.price ?? '-'))
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (r) => statusLabel(String(r.status || ''))
  },
  {
    title: '类型',
    key: 'order_role',
    width: 70,
    render: (r) => (String(r.order_role || 'sold') === 'bought' ? '买入' : '卖出')
  },
  { title: '时间', key: 'created_at', width: 150 },
  {
    title: '收货信息',
    key: 'receiver',
    width: 160,
    render: (r) =>
      h(
        'div',
        {
          style:
            'font-size:12px;line-height:1.35;white-space:normal;word-break:break-all;color:var(--n-text-color)'
        },
        [
          h('div', `收: ${dash(r.receiver_name)}`),
          h('div', `电: ${dash(r.receiver_phone)}`),
          h('div', `址: ${dash(r.receiver_address)}`)
        ]
      )
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    fixed: 'right',
    render: (r) =>
      h(
        NDropdown,
        {
          trigger: 'click',
          options: opOptions(r),
          onSelect: (k: string | number) => void onOp(k, r)
        },
        () => h(NButton, { size: 'tiny' }, () => '操作')
      )
  }
]

function mapPulledOrders(list: any[]): OrderRow[] {
  return (list || []).map((r) => ({
    order_id: r.order_id || r.id,
    id: r.order_id || r.id,
    item_id: r.item_id,
    item_title: r.item_title || r.title || '',
    item_pic: r.item_pic || r.pic_url || '',
    buyer_id: r.buyer_id,
    buyer_name: r.buyer_name || r.buyer_nick || '',
    buyer_nick: r.buyer_nick || r.buyer_name || '',
    receiver_name: r.receiver_name || '',
    receiver_phone: r.receiver_phone || '',
    receiver_address: r.receiver_address || '',
    quantity: r.quantity ?? r.num ?? 1,
    amount: r.amount ?? r.price,
    status: r.status || r.order_status || 'unknown',
    raw_status: r.raw_status || '',
    created_at: r.created_at || '',
    cookie_id: r.cookie_id || accountStore.activeCookieId
  }))
}

async function load(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const res = await getOrders({
      cookie_id: cookieId,
      status: status.value,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = res.data
    total.value = res.total
  } catch (e: any) {
    message.error(e?.message || '加载订单失败')
  } finally {
    loading.value = false
  }
}

/** 进入页面：先读缓存，本地为空则自动同步一次 */
async function bootstrap(): Promise<void> {
  await load()
  if (total.value === 0 && accountStore.activeCookieId) {
    await onSync()
  }
}

async function fillMissingReceivers(limit = 5, ids?: string[]): Promise<{ ok: number; fail: number; lastError: string }> {
  const targets =
    ids ||
    rows.value
      .filter((r) => !String(r.receiver_name || '').trim())
      .slice(0, limit)
      .map((r) => rowKey(r))
      .filter(Boolean)
  let ok = 0
  let fail = 0
  let lastError = ''
  for (const oid of targets) {
    try {
      await refreshSingleOrder(oid)
      ok += 1
    } catch (e: any) {
      fail += 1
      lastError = e?.message || String(e)
    }
  }
  if (ok) await load()
  return { ok, fail, lastError }
}

async function onFillReceivers(): Promise<void> {
  const selected = checked.value.map(String).filter(Boolean)
  const missing = rows.value
    .filter((r) => !String(r.receiver_name || '').trim())
    .map((r) => rowKey(r))
    .filter(Boolean)
  const targets = selected.length ? selected : missing.slice(0, 5)
  if (!targets.length) {
    message.info('没有需要补全的订单')
    return
  }
  fillingReceiver.value = true
  try {
    const { ok, fail, lastError } = await fillMissingReceivers(5, targets.slice(0, 20))
    if (ok) message.success(`已补全 ${ok} 条收货信息`)
    else message.warning(lastError || '补全未成功，可能平台未返回地址或 Cookie 失效')
    if (fail && ok) message.info(`${fail} 条未能补全`)
  } finally {
    fillingReceiver.value = false
  }
}

async function onSync(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    message.warning('请先选择账号')
    return
  }
  syncing.value = true
  hint.value = ''
  try {
    const st = status.value === 'all' ? undefined : status.value
    const pull = await pullOrders(cookieId, st)
    await syncOrders(cookieId, st)
    const fetched = Number(pull?.fetched ?? 0)
    const saved = Number(pull?.saved ?? 0)
    const pulledList = pull?.orders || pull?.details?.[0]?.orders || []
    await load()
    if (total.value === 0 && Array.isArray(pulledList) && pulledList.length) {
      rows.value = mapPulledOrders(pulledList)
      total.value = rows.value.length
      hint.value = `已拉取 ${fetched} 条（入库 ${saved}）。列表已临时展示拉取结果；若入库为 0，请查看后台日志中的 diagnostics。`
    } else if (fetched === 0 && total.value === 0) {
      hint.value =
        pull?.message ||
        '平台「我卖出的」列表接口可能受限。新成交仍可能通过聊天自动入库。'
      message.warning('暂未拉到新订单')
    } else {
      const diag = (pull?.diagnostics || []).slice(-3).join('；')
      message.success(
        `同步完成：获取 ${fetched}，入库 ${saved}，当前列表 ${total.value} 条${diag ? '；' + diag : ''}`
      )
      const missing = rows.value.filter((r) => !String(r.receiver_name || '').trim()).length
      if (missing > 0) {
        void fillMissingReceivers(5).then((r) => {
          if (r.ok) message.info(`已后台补全 ${r.ok} 条收货信息`)
        })
      }
    }
  } catch (e: any) {
    message.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function onAccountChange(): Promise<void> {
  page.value = 1
  await load()
}

async function onBatchShip(): Promise<void> {
  if (!checked.value.length) return
  try {
    await manualShipOrder(checked.value.map(String), 'manual')
    message.success('已批量提交发货')
    await load()
  } catch (e: any) {
    message.error(e?.message || '批量发货失败')
  }
}

function onBatchDelete(): void {
  if (!checked.value.length) return
  dialog.warning({
    title: '批量删除',
    content: `确定删除选中的 ${checked.value.length} 个订单吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      for (const id of checked.value) {
        try {
          await deleteOrder(String(id))
        } catch {
          /* continue */
        }
      }
      checked.value = []
      message.success('已删除')
      await load()
    }
  })
}

function onPageChange(p: number): void {
  page.value = p
  void load()
}

function onPageSizeChange(ps: number): void {
  pageSize.value = ps
  page.value = 1
  void load()
}

watch(status, () => {
  page.value = 1
  void load()
})

onMounted(() => {
  void bootstrap()
})
</script>

<template>
  <n-card title="订单管理" size="small">
    <AccountTabs :show-unread="false" @change="onAccountChange" />
    <n-space style="margin-bottom: 12px" align="center">
      <n-select
        v-model:value="status"
        :options="statusOptions"
        style="width: 140px"
      />
      <n-button type="primary" :loading="syncing" @click="onSync">一键同步</n-button>
      <n-button secondary :loading="fillingReceiver" @click="onFillReceivers">补全收货信息</n-button>
      <n-button secondary :disabled="!checked.length" @click="onBatchShip">批量发货</n-button>
      <n-button secondary type="error" :disabled="!checked.length" @click="onBatchDelete"
        >批量删除</n-button
      >
      <n-text depth="3">共 {{ total }} 条 · 已选 {{ checked.length }}</n-text>
    </n-space>
    <n-text depth="3" style="display: block; margin-bottom: 8px; font-size: 12px">
      进入自动加载本地缓存；若为空会自动同步。翻页/筛选读本地数据，一键同步用于从平台拉取最新。
    </n-text>
    <n-text v-if="hint" type="warning" style="display: block; margin-bottom: 8px; font-size: 12px">
      {{ hint }}
    </n-text>
    <n-data-table
      v-model:checked-row-keys="checked"
      :loading="loading"
      :columns="columns"
      :data="rows"
      :bordered="false"
      size="small"
      :row-key="rowKey"
      :scroll-x="1200"
      flex-height
      style="height: calc(100vh - 280px)"
    />
    <n-space justify="end" style="margin-top: 12px" v-if="total > 0">
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        :page-sizes="pageSizeOptions"
        show-size-picker
        show-quick-jumper
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </n-space>
  </n-card>

  <n-drawer v-model:show="detailShow" :width="480">
    <n-drawer-content title="订单详情" closable>
      <pre style="white-space: pre-wrap; word-break: break-all; font-size: 12px">{{ detailJson }}</pre>
    </n-drawer-content>
  </n-drawer>
</template>
