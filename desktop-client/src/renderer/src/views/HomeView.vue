<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NAvatar,
  NButton,
  NCard,
  NGi,
  NGrid,
  NImage,
  NModal,
  NSpace,
  NStatistic,
  NTag,
  NText,
  useMessage
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import { getAccountOverview, reconnectAccount, type AccountOverview } from '../api/overview'
import { generateQRLogin, checkQRLoginStatus } from '../api/qr'
import { refreshAccountProfile } from '../api/accounts'

const message = useMessage()
const router = useRouter()
const accountStore = useAccountStore()
const overview = ref<AccountOverview | null>(null)
const loading = ref(false)
const reconnecting = ref(false)
let timer: number | null = null

const reauthShow = ref(false)
const qrUrl = ref('')
const qrSessionId = ref('')
const qrStatus = ref('')
const qrLoading = ref(false)
let qrTimer: ReturnType<typeof setInterval> | null = null
let reauthPolling = false
let reauthFinished = false

async function load(): Promise<void> {
  const id = accountStore.activeCookieId
  if (!id) {
    overview.value = null
    return
  }
  loading.value = true
  try {
    const list = await getAccountOverview(id)
    overview.value = list[0] || null
    void accountStore.loadAccounts()
  } catch {
    overview.value = null
  } finally {
    loading.value = false
  }
}

async function onReconnect(): Promise<void> {
  const id = accountStore.activeCookieId
  if (!id) return
  if (overview.value?.need_reauth || overview.value?.auth_action === 'reauth') {
    message.warning('当前是闲鱼官方风控/登录态异常，请使用「重新授权」扫码，重连通常无效')
    openReauth()
    return
  }
  reconnecting.value = true
  try {
    const res = await reconnectAccount(id)
    if (res?.need_reauth) {
      message.warning(res.message || '需要重新扫码授权')
      openReauth()
      return
    }
    message.success(res?.message || '已触发重连，正在等待消息通道…')
    const ok = await waitUntilOnline(id, 8)
    if (ok) message.success('消息通道已在线')
    else message.warning('仍显示离线。若反复掉线，请点「重新授权」扫码登录')
  } catch (e: any) {
    message.error(e?.message || '重连失败')
  } finally {
    reconnecting.value = false
  }
}

function clearQrTimer(): void {
  if (qrTimer) {
    clearInterval(qrTimer)
    qrTimer = null
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/** 轮询概览直到在线；由调用方统一弹最终提示 */
async function waitUntilOnline(id: string, rounds = 12): Promise<boolean> {
  for (let i = 0; i < rounds; i++) {
    await sleep(2000)
    await load()
    if (overview.value?.online) return true
  }
  return false
}

async function openReauth(): Promise<void> {
  reauthShow.value = true
  await startReauthQr()
}

async function startReauthQr(): Promise<void> {
  clearQrTimer()
  reauthPolling = false
  reauthFinished = false
  qrLoading.value = true
  qrUrl.value = ''
  qrSessionId.value = ''
  qrStatus.value = '正在生成二维码…'
  try {
    const res = await generateQRLogin()
    if (!res.success || !res.session_id || !res.qr_code_url) {
      qrStatus.value = res.message || '二维码生成失败'
      message.error(qrStatus.value)
      return
    }
    qrSessionId.value = res.session_id
    qrUrl.value = res.qr_code_url
    qrStatus.value = '请使用闲鱼 App 扫码重新授权当前账号'
    qrTimer = setInterval(() => void pollReauth(), 1000)
  } catch (e: any) {
    qrStatus.value = e?.message || '生成失败'
    message.error(qrStatus.value)
  } finally {
    qrLoading.value = false
  }
}

async function finishReauthSuccess(id: string, nick: string): Promise<void> {
  // 先关掉弹窗，立刻清掉首页风控横幅（避免旧状态闪一下）
  reauthShow.value = false
  if (overview.value) {
    overview.value = {
      ...overview.value,
      need_reauth: false,
      auth_action: 'none',
      official_message: '',
      health_reason: '正在连接消息通道…',
      online: false
    }
  }
  if (id) {
    try {
      await refreshAccountProfile(id)
    } catch {
      /* ignore */
    }
    accountStore.setActive(id)
  }
  try {
    if (id) await reconnectAccount(id, true)
  } catch {
    /* ignore */
  }
  const online = await waitUntilOnline(id, 12)
  if (online) {
    message.success(nick ? `重新授权成功：${nick}，消息通道已在线` : '重新授权成功，消息通道已在线')
  } else {
    message.warning(
      nick
        ? `重新授权成功：${nick}。消息通道仍在连接，请稍候查看首页状态`
        : '重新授权成功。消息通道仍在连接，请稍候查看首页状态'
    )
  }
}

async function pollReauth(): Promise<void> {
  if (!qrSessionId.value || reauthFinished || reauthPolling) return
  reauthPolling = true
  try {
    const st = await checkQRLoginStatus(qrSessionId.value)
    if (st.status === 'scanned') {
      qrStatus.value = '已扫码，请在手机上确认'
      return
    }
    if (st.status === 'processing') {
      qrStatus.value = '正在处理登录…'
      return
    }
    if (st.status === 'expired') {
      qrStatus.value = '二维码已过期，正在刷新…'
      clearQrTimer()
      void startReauthQr()
      return
    }
    // already_processed：本次会话已处理过，忽略（防连弹）；仅认第一次 success
    if (st.status === 'already_processed') {
      return
    }
    const success = st.success === true || st.status === 'success'
    if (!success) return

    reauthFinished = true
    clearQrTimer()
    const info = st.account_info || {}
    const id = info.account_id || accountStore.activeCookieId || ''
    const nick = info.nickname || ''
    await finishReauthSuccess(id, nick)
  } catch (e) {
    console.warn(e)
  } finally {
    reauthPolling = false
  }
}

function closeReauth(): void {
  clearQrTimer()
  reauthShow.value = false
  reauthFinished = false
  reauthPolling = false
}

function go(name: string): void {
  void router.push({ name })
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => void load(), 8000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
  clearQrTimer()
})

watch(
  () => accountStore.activeCookieId,
  () => void load()
)
</script>

<template>
  <n-card title="首页" size="small">
    <AccountTabs @change="load" />
    <n-space align="center" style="margin: 8px 0 12px" :wrap="true">
      <n-text depth="3">当前账号数据概览（约 8 秒刷新在线状态）</n-text>
      <n-tag
        v-if="overview"
        size="small"
        :type="overview.online ? 'success' : 'error'"
        round
      >
        {{ overview.online ? '在线' : '离线' }}
      </n-tag>
      <n-button
        v-if="overview && (overview.need_reauth || overview.auth_action === 'reauth')"
        size="tiny"
        type="error"
        @click="openReauth"
      >
        重新授权
      </n-button>
      <n-button
        v-if="overview && !overview.online && overview.auth_action !== 'reauth' && !overview.need_reauth"
        size="tiny"
        type="warning"
        :loading="reconnecting"
        @click="onReconnect"
      >
        重连消息通道
      </n-button>
    </n-space>

    <n-alert
      v-if="overview && (overview.need_reauth || (overview.official_message && !overview.online))"
      type="warning"
      :bordered="false"
      style="margin-bottom: 12px"
      title="闲鱼官方状态"
    >
      <div style="line-height: 1.6">
        {{ overview.official_message || overview.health_reason }}
      </div>
      <n-button size="small" type="primary" style="margin-top: 8px" @click="openReauth">
        扫码重新授权
      </n-button>
    </n-alert>
    <n-text
      v-else-if="overview?.health_reason && overview.health_reason !== '在线'"
      depth="3"
      style="display: block; margin-bottom: 12px; font-size: 12px"
    >
      {{ overview.health_reason }}
    </n-text>

    <div v-if="overview" class="account-hero">
      <n-avatar round :size="48" :src="overview.avatar_url" />
      <div>
        <n-text strong style="font-size: 16px">{{ overview.nickname }}</n-text>
        <n-text depth="3" style="display: block; font-size: 12px">{{ overview.cookie_id }}</n-text>
        <n-space :size="6" style="margin-top: 6px" :wrap="true">
          <n-tag v-if="overview.auto_confirm" size="small" type="primary" round>自动确认发货</n-tag>
          <n-tag v-if="overview.daily_polish" size="small" type="info" round>每日擦亮</n-tag>
          <n-tag v-if="overview.auto_review" size="small" type="success" round>自动评价</n-tag>
          <n-tag v-if="overview.ai_enabled" size="small" type="warning" round>AI 议价</n-tag>
        </n-space>
      </div>
    </div>

    <n-text strong style="display: block; margin: 16px 0 8px">今日经营</n-text>
    <n-grid cols="2 s:3 m:6" responsive="screen" :x-gap="12" :y-gap="12">
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="今日订单" :value="overview?.today_orders ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="今日支付金额" :value="overview?.today_amount ?? 0">
            <template #prefix>¥</template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="今日取消订单" :value="overview?.today_cancelled ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('items')">
          <n-statistic label="宝贝浏览合计" :value="overview?.exposure ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('items')">
          <n-statistic label="在售商品数" :value="overview?.item_count ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('messages')">
          <n-statistic label="会话数" :value="overview?.session_count ?? 0" />
        </n-card>
      </n-gi>
    </n-grid>

    <n-text strong style="display: block; margin: 20px 0 8px">待办事项</n-text>
    <n-text depth="3" style="display: block; margin: 0 0 8px; font-size: 12px">
      数据来自本机订单库与会话库真实统计。「待回复」= 近 7 天内、最近一条仍是买家消息的会话（你本地回复后会减少）。点卡片可跳转查看。
    </n-text>
    <n-grid cols="2 s:3 m:6" responsive="screen" :x-gap="12" :y-gap="12">
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('messages')">
          <n-statistic label="待回复会话" :value="overview?.unread_sessions ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="待付款" :value="overview?.pending_pay ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="待发货" :value="overview?.pending_ship ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="已发货待收货" :value="overview?.shipped ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="退款中" :value="overview?.refunding ?? 0" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card" hoverable @click="go('orders')">
          <n-statistic label="待评价" :value="overview?.pending_review ?? 0" />
        </n-card>
      </n-gi>
    </n-grid>

    <n-text
      v-if="overview && (overview.need_reauth || overview.auth_action === 'reauth')"
      depth="3"
      style="display: block; margin-top: 12px; font-size: 12px"
    >
      当前账号触发闲鱼官方风控或登录态失效，请点「重新授权」扫码更新 Cookie，不要反复点重连。
    </n-text>
    <n-text
      v-else-if="overview && !overview.online"
      depth="3"
      style="display: block; margin-top: 12px; font-size: 12px"
    >
      消息通道连接中。若长时间仍离线，再点「重新授权」扫码更新 Cookie。
    </n-text>
  </n-card>

  <n-modal
    v-model:show="reauthShow"
    preset="card"
    title="重新授权 · 扫码登录"
    style="width: 420px"
    :mask-closable="false"
    @after-leave="closeReauth"
  >
    <n-text depth="3" style="display: block; margin-bottom: 12px; font-size: 13px">
      用闲鱼 App 扫描下方二维码，确认后会更新本账号 Cookie 并重新拉起消息通道。这与「重连」不同：重连只用旧票，无法解除官方风控。
    </n-text>
    <div style="display: flex; flex-direction: column; align-items: center; gap: 10px">
      <n-image
        v-if="qrUrl"
        :src="qrUrl"
        width="220"
        height="220"
        object-fit="contain"
        style="border: 1px solid #eee; border-radius: 8px"
      />
      <n-text v-else depth="3">{{ qrLoading ? '生成中…' : '暂无二维码' }}</n-text>
      <n-text style="font-size: 13px">{{ qrStatus }}</n-text>
      <n-space>
        <n-button size="small" :loading="qrLoading" @click="startReauthQr">刷新二维码</n-button>
        <n-button size="small" @click="closeReauth">关闭</n-button>
      </n-space>
    </div>
  </n-modal>
</template>

<style scoped>
.account-hero {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}
.stat-card {
  cursor: pointer;
}
.stat-card:hover {
  border-color: #18a058;
}
</style>
