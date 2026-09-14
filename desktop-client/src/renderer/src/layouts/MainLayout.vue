<script setup lang="ts">
import type { Component } from 'vue'
import { computed, h, onErrorCaptured, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NBadge,
  NBreadcrumb,
  NBreadcrumbItem,
  NButton,
  NDropdown,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutFooter,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NSpace,
  NText,
  NTooltip,
  useDialog,
  useMessage,
  type MenuOption
} from 'naive-ui'
import {
  Chatbubbles,
  Cube,
  DocumentText,
  EyeOutline,
  FitnessOutline,
  Grid,
  HeartOutline,
  KeyOutline,
  Megaphone,
  MoonOutline,
  Notifications,
  Receipt,
  Search,
  Settings,
  Storefront,
  SunnyOutline,
  ChatboxEllipsesOutline,
  WarningOutline
} from '@vicons/ionicons5'
import { useAuthStore } from '../stores/auth'
import { useAccountStore } from '../stores/account'
import { useThemeStore } from '../stores/theme'
import { useChatUnreadStore, unlockChatAudio } from '../stores/chatUnread'
import { useGlobalChatWs } from '../composables/useGlobalChatWs'
import { useGlobalSessionSync } from '../composables/useGlobalSessionSync'
import { useAccountOnlineGuard } from '../composables/useAccountOnlineGuard'
import { setWindowMode } from '../utils/windowMode'

const APP_VERSION = 'v2.0.0.1'

const auth = useAuthStore()
const accountStore = useAccountStore()
const themeStore = useThemeStore()
const unread = useChatUnreadStore()
const router = useRouter()
const route = useRoute()
const message = useMessage()
const dialog = useDialog()
const collapsed = ref(false)
const expandedKeys = ref<string[]>([])
const viewError = ref('')
const viewEpoch = ref(0)

onErrorCaptured((err) => {
  const msg = err instanceof Error ? err.message : String(err || '页面渲染异常')
  viewError.value = msg
  console.error('[MainLayout] view error', err)
  message.error(`页面出错：${msg.slice(0, 80)}`)
  return false
})

watch(
  () => route.fullPath,
  () => {
    viewError.value = ''
  }
)

function recoverView(): void {
  viewError.value = ''
  viewEpoch.value += 1
}

function onExpandedKeysUpdate(keys: string[]): void {
  // 手风琴：只保留最新展开的一个一级菜单
  if (!keys.length) {
    expandedKeys.value = []
    return
  }
  const prev = new Set(expandedKeys.value)
  const added = keys.filter((k) => !prev.has(k))
  expandedKeys.value = added.length ? [added[added.length - 1]] : [keys[keys.length - 1]]
}

useGlobalChatWs()
useGlobalSessionSync(45000)
useAccountOnlineGuard(30000)

function renderColorIcon(icon: Component, color: string) {
  return () => h(NIcon, { size: 18, color }, { default: () => h(icon) })
}

const menuOptions = computed<MenuOption[]>(() => [
  { label: '首页', key: 'home', icon: renderColorIcon(Grid, '#18a058') },
  {
    label: () =>
      h('div', { style: 'display: flex; align-items: center; gap: 8px;' }, [
        h('span', '消息'),
        unread.count > 0 ? h(NBadge, { value: unread.count, max: 99 }) : null
      ]),
    key: 'messages',
    icon: renderColorIcon(Chatbubbles, '#2080f0')
  },
  {
    label: '销售管理',
    key: 'sales',
    icon: renderColorIcon(Storefront, '#f0a020'),
    children: [
      { label: '订单管理', key: 'orders', icon: renderColorIcon(Receipt, '#d03050') },
      { label: '卡密库存', key: 'cards-inventory', icon: renderColorIcon(KeyOutline, '#18a058') },
      { label: '发货模板', key: 'ship-templates', icon: renderColorIcon(DocumentText, '#8a2be2') },
      { label: '商品管理', key: 'items', icon: renderColorIcon(Cube, '#36ad6a') }
    ]
  },
  {
    label: '营销管理',
    key: 'marketing',
    icon: renderColorIcon(Megaphone, '#e88080'),
    children: [
      { label: '采集管理', key: 'collect', icon: renderColorIcon(Search, '#2080f0') },
      { label: '卖家监控', key: 'seller-watch', icon: renderColorIcon(EyeOutline, '#18a058') },
      { label: '养号助手', key: 'yanghao', icon: renderColorIcon(FitnessOutline, '#8a2be2') },
      { label: '敏感词检测', key: 'sensitive-words', icon: renderColorIcon(WarningOutline, '#d03050') },
      { label: '发布商品', key: 'publish', icon: renderColorIcon(Storefront, '#f0a020') },
      { label: '我的收藏', key: 'favorites', icon: renderColorIcon(HeartOutline, '#d03050') }
    ]
  },
  {
    label: '通知管理',
    key: 'notify',
    icon: renderColorIcon(Notifications, '#f2c97d'),
    children: [
      { label: '通知设置', key: 'notify-settings', icon: renderColorIcon(Settings, '#7f7f7f') },
      { label: '关键词回复', key: 'keyword-reply', icon: renderColorIcon(KeyOutline, '#2080f0') },
      {
        label: '商品回复',
        key: 'item-reply',
        icon: renderColorIcon(ChatboxEllipsesOutline, '#18a058')
      }
    ]
  },
  { label: '系统设置', key: 'settings', icon: renderColorIcon(Settings, '#666') }
])

const titleMap: Record<string, string> = {
  home: '首页',
  messages: '消息',
  sales: '销售管理',
  orders: '订单管理',
  'cards-inventory': '卡密库存',
  'ship-templates': '发货模板',
  items: '商品管理',
  marketing: '营销管理',
  collect: '采集管理',
  'seller-watch': '卖家监控',
  yanghao: '养号助手',
  'sensitive-words': '敏感词检测',
  publish: '发布商品',
  favorites: '我的收藏',
  'keyword-reply': '关键词回复',
  'item-reply': '商品回复',
  notify: '通知管理',
  'notify-settings': '通知设置',
  settings: '系统设置'
}

const parentOf: Record<string, string> = {
  orders: 'sales',
  'cards-inventory': 'sales',
  'ship-templates': 'sales',
  items: 'sales',
  collect: 'marketing',
  'seller-watch': 'marketing',
  yanghao: 'marketing',
  'sensitive-words': 'marketing',
  publish: 'marketing',
  favorites: 'marketing',
  'keyword-reply': 'notify',
  'item-reply': 'notify',
  'notify-settings': 'notify'
}

const activeKey = computed(() => String(route.name || 'home'))

const breadcrumbItems = computed(() => {
  const key = activeKey.value
  const items: { key: string; label: string }[] = [{ key: 'home', label: '首页' }]
  if (key === 'home') return items
  const parent = parentOf[key]
  if (parent) items.push({ key: parent, label: titleMap[parent] || parent })
  items.push({ key, label: titleMap[key] || key })
  return items
})

function onMenuUpdate(key: string): void {
  if (key === 'sales' || key === 'notify' || key === 'marketing') return
  router.push({ name: key })
}

const userOptions = [
  { label: '切换账号列表', key: 'switch' },
  { label: '退出登录', key: 'logout' }
]

async function onUserSelect(key: string | number): Promise<void> {
  if (key === 'logout') {
    dialog.warning({
      title: '确认退出',
      content: '退出后将离开工作台，是否继续？',
      positiveText: '退出',
      negativeText: '取消',
      onPositiveClick: async () => {
        sessionStorage.removeItem('xy_entered_workbench')
        localStorage.removeItem('xy_auto_workbench')
        accountStore.setActive('')
        await auth.logout()
        message.success('已登出')
        try {
          await setWindowMode('login')
        } catch {
          /* ignore */
        }
        await router.replace({ name: 'login', query: { switch: '1' } })
      }
    })
  } else if (key === 'switch') {
    dialog.info({
      title: '切换账号',
      content: '将返回账号列表，可重新选择或添加闲鱼账号。',
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        sessionStorage.removeItem('xy_entered_workbench')
        localStorage.setItem('xy_auto_workbench', '0')
        try {
          await setWindowMode('login')
        } catch {
          /* ignore */
        }
        await router.replace({ name: 'login', query: { switch: '1' } })
      }
    })
  }
}

function checkUpdate(): void {
  dialog.success({
    title: '检查更新',
    content: `当前已是最新版本（${APP_VERSION}）`,
    positiveText: '我知道了'
  })
}

onMounted(async () => {
  await setWindowMode('workbench')
  void unlockChatAudio()
  document.addEventListener('click', () => void unlockChatAudio(), { once: true })
  try {
    await accountStore.loadAccounts()
  } catch {
    /* ignore */
  }
})
</script>

<template>
  <n-layout class="app-shell" position="absolute">
    <n-layout-header bordered class="app-header">
      <div class="header-left">
        <n-breadcrumb>
          <n-breadcrumb-item
            v-for="(item, idx) in breadcrumbItems"
            :key="item.key"
            :clickable="idx === 0 && breadcrumbItems.length > 1"
            @click="
              idx === 0 && breadcrumbItems.length > 1 ? router.push({ name: 'home' }) : undefined
            "
          >
            {{ item.label }}
          </n-breadcrumb-item>
        </n-breadcrumb>
      </div>

      <n-space align="center" :size="8">
        <n-tooltip>
          <template #trigger>
            <n-button quaternary circle @click="themeStore.toggle()">
              <template #icon>
                <n-icon
                  :component="themeStore.mode === 'dark' ? SunnyOutline : MoonOutline"
                  :size="18"
                />
              </template>
            </n-button>
          </template>
          {{ themeStore.mode === 'dark' ? '切换浅色主题' : '切换深色主题' }}
        </n-tooltip>
        <n-dropdown :options="userOptions" @select="onUserSelect">
          <n-button quaternary size="small">更多</n-button>
        </n-dropdown>
      </n-space>
    </n-layout-header>

    <n-layout has-sider position="absolute" style="top: 52px; bottom: 40px">
      <n-layout-sider
        bordered
        show-trigger
        collapse-mode="width"
        :collapsed-width="64"
        :width="220"
        :collapsed="collapsed"
        :native-scrollbar="false"
        @update:collapsed="collapsed = $event"
      >
        <n-menu
          :collapsed="collapsed"
          :collapsed-width="64"
          :collapsed-icon-size="22"
          :value="activeKey"
          :options="menuOptions"
          :expanded-keys="expandedKeys"
          :accordion="true"
          @update:value="onMenuUpdate"
          @update:expanded-keys="onExpandedKeysUpdate"
        />
      </n-layout-sider>

      <n-layout-content
        content-style="padding: 16px;"
        :native-scrollbar="false"
        class="app-content"
      >
        <n-space v-if="viewError" vertical :size="12" style="padding: 32px 8px">
          <n-text type="error">页面渲染出错，已拦截以免整站空白。</n-text>
          <n-text depth="3" style="font-size: 12px; word-break: break-all">{{ viewError }}</n-text>
          <n-space>
            <n-button type="primary" @click="recoverView">重新加载本页</n-button>
            <n-button secondary @click="router.push({ name: 'home' })">回首页</n-button>
          </n-space>
        </n-space>
        <router-view v-else :key="`${String(route.name)}-${viewEpoch}`" />
      </n-layout-content>
    </n-layout>

    <n-layout-footer bordered class="app-footer">
      <n-space align="center" :size="8">
        <n-button size="tiny" quaternary @click="checkUpdate">检查更新</n-button>
        <n-text depth="3" style="font-size: 12px">{{ APP_VERSION }}</n-text>
      </n-space>
      <n-text depth="3" style="font-size: 12px">闲鱼管家桌面客户端</n-text>
    </n-layout-footer>
  </n-layout>
</template>

<style scoped>
.app-shell {
  inset: 0;
  background: var(--app-bg);
}

.app-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  box-sizing: border-box;
  background: var(--app-bg-elevated);
}

.header-left {
  padding-left: 12px;
  min-width: 0;
}

.app-content {
  background: var(--app-bg) !important;
}

.app-footer {
  height: 40px;
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  box-sizing: border-box;
  background: var(--app-bg-elevated);
}
</style>
