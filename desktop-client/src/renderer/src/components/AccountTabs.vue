<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch } from 'vue'
import { NAvatar, NBadge, NEmpty, NSpin, NTabPane, NTabs, NText } from 'naive-ui'
import { useAccountStore } from '../stores/account'
import { useChatUnreadStore } from '../stores/chatUnread'

const props = withDefaults(
  defineProps<{
    syncGlobal?: boolean
    showUnread?: boolean
  }>(),
  { syncGlobal: true, showUnread: true }
)

const emit = defineEmits<{
  change: [cookieId: string]
}>()

const accountStore = useAccountStore()
const unread = useChatUnreadStore()
let pollTimer: number | null = null

function onUpdate(value: string | number): void {
  const id = String(value)
  if (props.syncGlobal) accountStore.setActive(id)
  emit('change', id)
}

onMounted(() => {
  if (!accountStore.accounts.length) {
    void accountStore.loadAccounts().then(() => {
      if (accountStore.activeCookieId) emit('change', accountStore.activeCookieId)
    })
  } else if (accountStore.activeCookieId) {
    emit('change', accountStore.activeCookieId)
  }
  // 定期刷新在线状态
  pollTimer = window.setInterval(() => {
    void accountStore.loadAccounts()
  }, 15000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

watch(
  () => accountStore.activeCookieId,
  (id) => {
    if (id) emit('change', id)
  }
)
</script>

<template>
  <div class="account-tabs-wrap">
    <n-spin :show="accountStore.loading">
      <n-empty
        v-if="!accountStore.loading && !accountStore.accounts.length"
        description="暂无绑定账号，请先扫码登录"
        size="small"
      />
      <n-tabs
        v-else
        type="card"
        size="small"
        :value="accountStore.activeCookieId"
        @update:value="onUpdate"
      >
        <n-tab-pane v-for="a in accountStore.accounts" :key="a.id" :name="a.id" :tab="a.id">
          <template #tab>
            <n-badge
              :value="showUnread ? unread.cookieUnread(a.id) : 0"
              :max="99"
              :show="showUnread && unread.cookieUnread(a.id) > 0"
            >
              <div class="tab-label">
                <div class="avatar-wrap">
                  <n-avatar round :size="22" :src="a.avatar_url" />
                  <span
                    class="online-dot"
                    :class="a.online ? 'on' : 'off'"
                    :title="a.online ? '在线' : '离线'"
                  />
                </div>
                <n-text style="max-width: 100px; overflow: hidden; text-overflow: ellipsis">
                  {{ a.nickname || a.id }}
                </n-text>
              </div>
            </n-badge>
          </template>
        </n-tab-pane>
      </n-tabs>
    </n-spin>
  </div>
</template>

<style scoped>
.account-tabs-wrap {
  margin-bottom: 12px;
}
.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding-right: 4px;
}
.avatar-wrap {
  position: relative;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.online-dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid #fff;
  box-sizing: border-box;
}
.online-dot.on {
  background: #18a058;
}
.online-dot.off {
  background: #d03050;
}
</style>
