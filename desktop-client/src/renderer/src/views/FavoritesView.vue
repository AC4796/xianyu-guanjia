<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NImage,
  NSpace,
  NTag,
  NText,
  useMessage,
  type DataTableColumns,
  type DataTableRowKey
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  loadFavorites,
  removeFavorite,
  saveFavorites,
  type FavoriteItem
} from '../stores/favorites'
import { getPublishDetail } from '../api/items'

type FavStatus = 'unknown' | 'online' | 'offline' | 'checking'

interface FavRow extends FavoriteItem {
  status?: FavStatus
}

const message = useMessage()
const accountStore = useAccountStore()
const rows = ref<FavRow[]>([])
const checked = ref<DataTableRowKey[]>([])
const checking = ref(false)

function reload(): void {
  const cid = accountStore.activeCookieId
  rows.value = cid ? (loadFavorites(cid) as FavRow[]) : []
  checked.value = []
}

function openItem(r: FavoriteItem): void {
  const url = r.item_url || `https://www.goofish.com/item?id=${r.item_id}`
  window.open(url, '_blank')
}

async function copyLink(r: FavoriteItem): Promise<void> {
  const url = r.item_url || `https://www.goofish.com/item?id=${r.item_id}`
  try {
    await navigator.clipboard.writeText(url)
    message.success('已复制链接')
  } catch {
    message.error('复制失败')
  }
}

function unfav(r: FavoriteItem): void {
  const cid = accountStore.activeCookieId
  if (!cid) return
  rows.value = removeFavorite(cid, r.item_id)
  checked.value = checked.value.filter((k) => String(k) !== String(r.item_id))
  message.success('已取消收藏')
}

function batchUnfav(): void {
  const cid = accountStore.activeCookieId
  if (!cid) return
  if (!checked.value.length) {
    message.warning('请先勾选收藏')
    return
  }
  const drop = new Set(checked.value.map(String))
  const next = rows.value.filter((r) => !drop.has(String(r.item_id)))
  saveFavorites(cid, next)
  rows.value = next
  checked.value = []
  message.success(`已取消 ${drop.size} 条收藏`)
}

function unfavOffline(): void {
  const cid = accountStore.activeCookieId
  if (!cid) return
  const gone = rows.value.filter((r) => r.status === 'offline')
  if (!gone.length) {
    message.info('当前没有已标记为下架的收藏')
    return
  }
  const drop = new Set(gone.map((r) => String(r.item_id)))
  const next = rows.value.filter((r) => !drop.has(String(r.item_id)))
  saveFavorites(cid, next)
  rows.value = next
  checked.value = []
  message.success(`已取消 ${gone.length} 条下架商品收藏`)
}

function inferStatus(detail: Record<string, unknown> | undefined | null): FavStatus {
  if (!detail || typeof detail !== 'object') return 'offline'
  const ls = String(detail.local_status || detail.itemStatusText || '').toLowerCase()
  if (['off', 'down', 'offline', '下架', '已下架'].some((x) => ls.includes(x))) return 'offline'
  const st = detail.item_status ?? detail.itemStatus
  try {
    if (st !== undefined && st !== null && st !== '' && Number(st) !== 0) return 'offline'
  } catch {
    /* ignore */
  }
  const title = String(detail.title || detail.item_title || detail.itemTitle || '')
  if (!title && !detail.price && !detail.item_price) return 'offline'
  return 'online'
}

function persistStatuses(): void {
  const cid = accountStore.activeCookieId
  if (!cid) return
  const toSave: FavoriteItem[] = rows.value.map((r) => {
    const base: FavoriteItem = {
      item_id: r.item_id,
      title: r.title,
      price: r.price,
      main_image: r.main_image,
      item_url: r.item_url,
      seller_name: r.seller_name,
      saved_at: r.saved_at
    }
    if (r.status === 'online' || r.status === 'offline') base.status = r.status
    return base
  })
  saveFavorites(cid, toSave)
}

/** @param quiet 自动检测时不弹成功提示 */
async function checkOnlineStatus(quiet = false): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    if (!quiet) message.warning('请先选择账号')
    return
  }
  if (!rows.value.length) return
  if (checking.value) return
  checking.value = true
  rows.value = rows.value.map((r) => ({ ...r, status: 'checking' as FavStatus }))
  let offlineN = 0
  try {
    for (let i = 0; i < rows.value.length; i++) {
      const r = rows.value[i]
      try {
        const res = await getPublishDetail(cid, r.item_id)
        const data = (res as any)?.data || res
        const st = inferStatus(data as Record<string, unknown>)
        rows.value[i] = { ...r, status: st }
        if (st === 'offline') offlineN += 1
      } catch {
        rows.value[i] = { ...r, status: 'offline' }
        offlineN += 1
      }
    }
    persistStatuses()
    if (!quiet) {
      message.success(
        offlineN ? `检测完成：${offlineN} 件可能已下架，可一键取消收藏` : '检测完成：均在线或可访问'
      )
    }
  } finally {
    checking.value = false
  }
}

async function reloadAndCheck(): Promise<void> {
  reload()
  await checkOnlineStatus(true)
}

const columns = computed<DataTableColumns<FavRow>>(() => [
  { type: 'selection', width: 48 },
  {
    title: '缩略图',
    key: 'main_image',
    width: 72,
    render: (r) => {
      if (!r.main_image) return '-'
      return h(NImage, {
        src: r.main_image,
        width: 48,
        height: 48,
        objectFit: 'cover',
        style: 'border-radius:4px'
      })
    }
  },
  {
    title: '标题',
    key: 'title',
    ellipsis: { tooltip: true },
    render: (r) => r.title || r.item_id
  },
  {
    title: '价格',
    key: 'price',
    width: 90,
    render: (r) => String(r.price ?? '-')
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (r) => {
      if (r.status === 'checking' || (checking.value && r.status !== 'online' && r.status !== 'offline')) {
        return h(NTag, { size: 'small', type: 'info' }, () => '检测中')
      }
      if (r.status === 'online') return h(NTag, { size: 'small', type: 'success' }, () => '在线')
      if (r.status === 'offline') return h(NTag, { size: 'small', type: 'error' }, () => '已下架')
      return h(NTag, { size: 'small' }, () => '未检测')
    }
  },
  {
    title: '卖家',
    key: 'seller_name',
    width: 120,
    ellipsis: { tooltip: true },
    render: (r) => r.seller_name || '-'
  },
  {
    title: '收藏时间',
    key: 'saved_at',
    width: 170,
    render: (r) => {
      try {
        return r.saved_at ? new Date(r.saved_at).toLocaleString() : '-'
      } catch {
        return r.saved_at || '-'
      }
    }
  },
  {
    title: '操作',
    key: 'op',
    width: 260,
    render: (r) =>
      h(NSpace, { size: 6 }, () => [
        h(NButton, { size: 'tiny', onClick: () => openItem(r) }, () => '打开'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => void copyLink(r) }, () => '复制链接'),
        h(
          NButton,
          { size: 'tiny', type: 'error', secondary: true, onClick: () => unfav(r) },
          () => (r.status === 'offline' ? '下架·取消收藏' : '取消收藏')
        )
      ])
  }
])

watch(
  () => accountStore.activeCookieId,
  () => void reloadAndCheck()
)

onMounted(() => void reloadAndCheck())
</script>

<template>
  <n-card title="我的收藏" size="small">
    <AccountTabs :show-unread="false" @change="reloadAndCheck" />
    <n-space style="margin: 8px 0 12px" align="center">
      <n-button size="small" secondary :loading="checking" @click="checkOnlineStatus(false)"
        >检测在线状态</n-button
      >
      <n-button size="small" type="warning" secondary @click="unfavOffline"
        >一键取消已下架</n-button
      >
      <n-button
        size="small"
        type="error"
        secondary
        :disabled="!checked.length"
        @click="batchUnfav"
        >批量取消收藏</n-button
      >
      <n-text depth="3" style="font-size: 12px">
        已选 {{ checked.length }} · 收藏保存在本机；进入页面会自动检测在线状态
      </n-text>
    </n-space>
    <n-data-table
      v-model:checked-row-keys="checked"
      :columns="columns"
      :data="rows"
      size="small"
      :bordered="false"
      :row-key="(r) => r.item_id"
    />
    <n-text v-if="!rows.length" depth="3" style="display: block; margin-top: 16px; text-align: center">
      暂无收藏
    </n-text>
  </n-card>
</template>
