<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAvatar,
  NButton,
  NCard,
  NEmpty,
  NImage,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NModal,
  NSpace,
  NText,
  NTooltip,
  NH2,
  NP,
  NIcon,
  useDialog,
  useMessage
} from 'naive-ui'
import { AddOutline as AddIcon, InformationCircleOutline as InfoIcon } from '@vicons/ionicons5'
import logoUrl from '../assets/logo.png'
import { useAuthStore } from '../stores/auth'
import { useAccountStore } from '../stores/account'
import { checkQRLoginStatus, generateQRLogin } from '../api/qr'
import { getAccountDetails, refreshAccountProfile, type AccountCard } from '../api/accounts'
import { login as apiLogin } from '../api/auth'
import { setWindowMode } from '../utils/windowMode'

const auth = useAuthStore()
const accountStore = useAccountStore()
const router = useRouter()
const route = useRoute()
const message = useMessage()
const dialog = useDialog()
const APP_VERSION = 'v2.0.0.1'

type Step = 'accounts' | 'qr'
const step = ref<Step>('accounts')
const accounts = ref<AccountCard[]>([])
const loadingAccounts = ref(true)
const refreshing = ref(false)
const statusText = ref('准备中')
const qrUrl = ref('')
const sessionId = ref('')
const remainSeconds = ref(60)
const sessionReady = ref(false)
const showRiskModal = ref(false)
const siderWidth = ref(380)

function updateSiderWidth(): void {
  const w = typeof window !== 'undefined' ? window.innerWidth : 880
  siderWidth.value = Math.min(320, Math.max(220, Math.round(w * 0.34)))
}

let timer: ReturnType<typeof setInterval> | null = null
let polling = false
let countdownTimer: ReturnType<typeof setInterval> | null = null

function clearTimers(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

async function waitBackendReady(): Promise<boolean> {
  const ensure = window.api?.ensureBackend
  if (typeof ensure !== 'function') return true

  // 轮询状态文案，避免只卡在一句「启动中」
  let stopped = false
  const poll = window.setInterval(() => {
    void window.api?.getBackendStatus?.().then((st) => {
      if (!stopped && st?.message) statusText.value = st.message
    })
  }, 800)

  try {
    statusText.value = '正在准备本地服务…'
    const st = await ensure()
    if (st.ready) return true
    statusText.value = st.message || '本地服务未就绪'
    message.error(st.message || '本地服务未就绪', { duration: 6000 })
    return false
  } finally {
    stopped = true
    window.clearInterval(poll)
  }
}

async function ensureAdminSession(): Promise<boolean> {
  if (sessionReady.value && auth.authenticated) return true
  const backendOk = await waitBackendReady()
  if (!backendOk) return false
  await auth.refresh()
  if (auth.authenticated) {
    sessionReady.value = true
    return true
  }

  let res = await apiLogin({ username: 'admin', password: 'admin123' })
  if (!res.success && typeof window.api?.resetAdmin === 'function') {
    statusText.value = '正在修复本地账号…'
    await window.api.resetAdmin()
    await new Promise((r) => setTimeout(r, 600))
    res = await apiLogin({ username: 'admin', password: 'admin123' })
  }
  if (!res.success) {
    // 不对用户展示「用户名或密码错误」——那是内部会话账号，不是闲鱼账号
    const tip = '本地会话初始化失败，请点击「刷新二维码」重试'
    statusText.value = tip
    message.error(tip, { duration: 5000 })
    return false
  }
  await auth.refresh()
  sessionReady.value = auth.authenticated
  return sessionReady.value
}

async function loadAccounts(): Promise<void> {
  loadingAccounts.value = true
  try {
    // 调用方已保证会话；这里只拉账号，避免重复登录报错
    if (!sessionReady.value) {
      const ok = await ensureAdminSession()
      if (!ok) return
    }
    accounts.value = await getAccountDetails()
    for (const a of accounts.value.slice(0, 6)) {
      if (!a.nickname || !a.avatar_url || a.avatar_url.includes('dicebear')) {
        void refreshAccountProfile(a.id)
          .then(async () => {
            accounts.value = await getAccountDetails()
          })
          .catch(() => undefined)
      }
    }
  } catch (e: any) {
    message.error(e?.message || '加载账号失败')
  } finally {
    loadingAccounts.value = false
  }
}

function startCountdown(seconds: number): void {
  if (countdownTimer) clearInterval(countdownTimer)
  remainSeconds.value = Math.max(1, seconds || 60)
  countdownTimer = setInterval(() => {
    remainSeconds.value = Math.max(0, remainSeconds.value - 1)
    if (remainSeconds.value <= 0) {
      if (countdownTimer) clearInterval(countdownTimer)
      countdownTimer = null
      void startQr(true)
    }
  }, 1000)
}

async function startQr(isAuto = false): Promise<void> {
  clearTimers()
  step.value = 'qr'
  refreshing.value = true
  if (!isAuto) statusText.value = '正在生成二维码'
  else statusText.value = '二维码已过期，正在刷新…'
  try {
    const ok = await ensureAdminSession()
    if (!ok) {
      statusText.value = '会话未就绪'
      return
    }
    const res = await generateQRLogin()
    if (!res.success || !res.session_id || !res.qr_code_url) {
      message.error(res.message || '二维码生成失败')
      statusText.value = res.message || '生成失败'
      return
    }
    sessionId.value = res.session_id
    qrUrl.value = res.qr_code_url
    statusText.value = '请使用闲鱼 App 扫码'
    startCountdown(res.remain_seconds || res.expire_seconds || 60)
    timer = setInterval(() => {
      void pollStatus()
    }, 1000)
  } catch (e: any) {
    message.error(e?.message || '生成二维码失败')
    statusText.value = e?.message || '生成失败'
  } finally {
    refreshing.value = false
  }
}

async function pollStatus(): Promise<void> {
  if (!sessionId.value || polling) return
  polling = true
  try {
    const st = await checkQRLoginStatus(sessionId.value)
    if (typeof st.remain_seconds === 'number') {
      remainSeconds.value = st.remain_seconds
    }
    if (st.status === 'scanned') {
      statusText.value = '已扫码，请在手机上确认'
    } else if (st.status === 'expired') {
      statusText.value = '二维码已过期'
      clearTimers()
      void startQr(true)
      return
    }
    const success =
      st.success === true || st.status === 'success' || st.status === 'already_processed'
    if (success) {
      clearTimers()
      const info = st.account_info || {}
      const id = info.account_id || ''
      const nick = info.nickname || ''
      message.success(nick ? `已绑定：${nick}` : '账号已绑定并保存 Cookie')
      if (id) {
        try {
          await refreshAccountProfile(id)
        } catch {
          /* ignore */
        }
      }
      await loadAccounts()
      step.value = 'accounts'
      if (id) accountStore.setActive(id)
    }
  } catch (e) {
    console.warn(e)
  } finally {
    polling = false
  }
}

function openAddAccount(): void {
  void startQr(false)
}

function backToAccounts(): void {
  clearTimers()
  step.value = 'accounts'
  void loadAccounts()
}

function enterWorkbench(acc?: AccountCard): void {
  const target = acc || accounts.value[0]
  if (target) accountStore.setActive(target.id)
  sessionStorage.setItem('xy_entered_workbench', '1')
  localStorage.setItem('xy_auto_workbench', '1')
  void setWindowMode('workbench').then(() => {
    router.replace({ name: 'home' })
  })
}

const hasAccounts = computed(() => accounts.value.length > 0)

/** 一行最多 5 个；少量账号时居中 */
const accountGridClass = computed(() => {
  const n = accounts.value.length
  if (n <= 2) return 'acc-grid acc-grid--center'
  return 'acc-grid'
})

function checkUpdate(): void {
  dialog.success({
    title: '检查更新',
    content: `当前已是最新版本（${APP_VERSION}）`,
    positiveText: '我知道了'
  })
}

onMounted(async () => {
  await setWindowMode('login')
  updateSiderWidth()
  window.addEventListener('resize', updateSiderWidth)

  step.value = 'qr'
  statusText.value = '正在准备…'

  const ok = await ensureAdminSession()
  if (!ok) return

  await loadAccounts()
  if (!sessionReady.value) {
    statusText.value = statusText.value || '会话未就绪'
    return
  }

  const forceAccountList =
    String(route.query.switch || '') === '1' || localStorage.getItem('xy_auto_workbench') === '0'
  if (!forceAccountList && accounts.value.length) {
    enterWorkbench(
      accounts.value.find((a) => a.id === accountStore.activeCookieId) || accounts.value[0]
    )
    return
  }
  if (!accounts.value.length) {
    await startQr(false)
  } else {
    step.value = 'accounts'
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateSiderWidth)
  clearTimers()
})
</script>

<template>
  <n-layout has-sider style="height: 100vh; width: 100vw">
    <n-layout-sider
      :width="siderWidth"
      :native-scrollbar="false"
      bordered
      class="login-sider"
      content-style="height: 100%; display: flex; align-items: center; justify-content: center; padding: 24px;"
    >
      <n-space vertical align="center" :size="12" style="width: 100%">
        <n-image :src="logoUrl" width="72" height="72" object-fit="cover" preview-disabled />
        <n-h2 style="margin: 0; font-size: 22px">闲鱼管家</n-h2>
        <n-p depth="3" style="margin: 0; text-align: center; font-size: 13px">电脑端工作台 · 扫码绑定闲鱼账号</n-p>
      </n-space>

      <div class="update-entry">
        <n-button quaternary size="small" @click="checkUpdate">检查更新</n-button>
        <n-text depth="3" style="font-size: 12px">{{ APP_VERSION }}</n-text>
      </div>
    </n-layout-sider>

    <n-layout-content class="login-main">
      <div class="risk-top">
        <n-button quaternary size="small" @click="showRiskModal = true">
          <template #icon>
            <n-icon :component="InfoIcon" color="#2080f0" />
          </template>
          风控说明
        </n-button>
      </div>

      <div class="login-panel">
        <n-card v-if="step === 'accounts'" title="已绑定账号" :bordered="true" size="small">
          <n-empty
            v-if="!loadingAccounts && !accounts.length"
            :show-icon="false"
            description="暂无账号，请点击右下角加号扫码添加"
          />
          <div v-else :class="accountGridClass">
            <n-tooltip v-for="acc in accounts" :key="acc.id" trigger="hover" placement="top">
              <template #trigger>
                <button type="button" class="acc-item" @click="enterWorkbench(acc)">
                  <n-avatar :src="acc.avatar_url" :size="40" round />
                  <span class="acc-name">{{ acc.nickname || acc.id }}</span>
                  <span class="acc-id">{{ acc.id }}</span>
                </button>
              </template>
              <div>
                <div>{{ acc.nickname || acc.id }}</div>
                <div>ID：{{ acc.id }}</div>
                <div v-if="acc.bio">{{ acc.bio }}</div>
              </div>
            </n-tooltip>
          </div>

          <div class="acc-add">
            <n-button circle type="primary" @click="openAddAccount">
              <template #icon>
                <n-icon :component="AddIcon" />
              </template>
            </n-button>
          </div>
        </n-card>

        <n-card v-else title="扫码登录" :bordered="true" size="small">
          <n-space vertical align="center" :size="10">
            <n-image
              v-if="qrUrl"
              :src="qrUrl"
              width="200"
              height="200"
              object-fit="contain"
              preview-disabled
            />
            <n-empty v-else :show-icon="false" :description="statusText || '正在生成二维码…'" />
            <n-text v-if="qrUrl">{{ statusText }}</n-text>
            <n-text v-if="qrUrl" style="color: #ff0000">{{ remainSeconds }}s</n-text>
            <n-space>
              <n-button v-if="hasAccounts" secondary size="small" @click="backToAccounts">返回</n-button>
              <n-button secondary size="small" :loading="refreshing" :disabled="refreshing" @click="startQr(false)">
                刷新二维码
              </n-button>
            </n-space>
          </n-space>
        </n-card>
      </div>
    </n-layout-content>
  </n-layout>

  <n-modal
    v-model:show="showRiskModal"
    preset="card"
    title="多账号与风控说明"
    style="width: 440px; max-width: 92vw"
    :bordered="false"
    size="huge"
  >
    <n-p style="margin: 0; line-height: 1.7; color: #444">
      每个闲鱼号使用独立 Cookie 会话保存，不会混用登录态。建议：同一账号尽量固定网络环境；不要短时间批量频繁扫码/上下线；多号并发时错开启动间隔。异地/多开仍可能触发平台风控，本软件会按号隔离
      Cookie 并持久化，下次打开无需重复扫码。
    </n-p>
    <template #footer>
      <n-space justify="end">
        <n-button type="primary" @click="showRiskModal = false">我知道了</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.login-sider {
  position: relative;
  background: linear-gradient(165deg, #f7f8fa 0%, #eef1f5 100%);
}
.update-entry {
  position: absolute;
  left: 12px;
  bottom: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.login-main {
  position: relative;
  background: #fff;
}
.login-main :deep(.n-layout-scroll-container) {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 20px;
}
.risk-top {
  position: absolute;
  top: 10px;
  right: 12px;
  z-index: 2;
}
.login-panel {
  width: 420px;
  max-width: 100%;
}
.acc-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px 6px;
  min-height: 72px;
  align-content: start;
}
.acc-grid--center {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px 16px;
}
.acc-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 72px;
  padding: 6px 2px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
  font: inherit;
}
.acc-item:hover {
  background: #f0f7ff;
}
.acc-name {
  max-width: 68px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: normal;
  color: #333;
  line-height: 1.2;
}
.acc-id {
  max-width: 68px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  font-weight: normal;
  color: #999;
  line-height: 1.2;
}
.acc-add {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
