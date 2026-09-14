<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NAvatar,
  NButton,
  NCard,
  NDataTable,
  NSpace,
  NTag,
  NText,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import { reconnectAccount, type AccountCard } from '../api/accounts'

const message = useMessage()
const accountStore = useAccountStore()
const reconnectingId = ref('')

const rows = computed(() => accountStore.accounts)

async function refresh(): Promise<void> {
  try {
    await accountStore.loadAccounts()
  } catch (e: any) {
    message.error(e?.message || '刷新失败')
  }
}

async function onReconnect(row: AccountCard): Promise<void> {
  reconnectingId.value = row.id
  try {
    await reconnectAccount(row.id)
    message.success(`已触发重连：${row.nickname || row.id}`)
    await new Promise((r) => setTimeout(r, 5000))
    await refresh()
  } catch (e: any) {
    message.error(e?.message || '重连失败')
  } finally {
    reconnectingId.value = ''
  }
}

const columns: DataTableColumns<AccountCard> = [
  {
    title: '账号',
    key: 'nickname',
    render: (r) =>
      h(NSpace, { align: 'center', size: 8 }, () => [
        h(NAvatar, { round: true, size: 32, src: r.avatar_url }),
        h('div', [
          h('div', { style: 'font-weight:600' }, r.nickname || r.id),
          h('div', { style: 'font-size:12px;opacity:.65' }, r.id)
        ])
      ])
  },
  {
    title: '消息通道',
    key: 'online',
    width: 120,
    render: (r) =>
      h(
        NTag,
        { size: 'small', type: r.online ? 'success' : 'error', round: true },
        () => (r.online ? '在线' : '离线')
      )
  },
  {
    title: '启用',
    key: 'enabled',
    width: 90,
    render: (r) =>
      h(
        NTag,
        { size: 'small', type: r.enabled === false ? 'warning' : 'default' },
        () => (r.enabled === false ? '已禁用' : '启用')
      )
  },
  {
    title: '操作',
    key: 'op',
    width: 140,
    render: (r) =>
      h(
        NButton,
        {
          size: 'tiny',
          type: 'warning',
          secondary: true,
          loading: reconnectingId.value === r.id,
          onClick: () => void onReconnect(r)
        },
        () => '重连消息通道'
      )
  }
]

onMounted(() => {
  void refresh()
})
</script>

<template>
  <n-card title="账号管理" size="small">
    <AccountTabs @change="refresh" />
    <n-space style="margin: 8px 0 12px" align="center">
      <n-button size="small" secondary :loading="accountStore.loading" @click="refresh">刷新状态</n-button>
      <n-text depth="3" style="font-size: 12px">
        绿色在线 = 可发消息。频繁掉线/风控请回首页点「重新授权」扫码；仅短暂断线可点「重连消息通道」。
      </n-text>
    </n-space>
    <n-data-table
      :columns="columns"
      :data="rows"
      size="small"
      :bordered="false"
      :row-key="(r) => r.id"
    />
  </n-card>
</template>
