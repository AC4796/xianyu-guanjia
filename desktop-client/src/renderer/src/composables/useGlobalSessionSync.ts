/** 全局自动同步会话：不依赖是否打开消息页 */
import { onBeforeUnmount, onMounted } from 'vue'
import { syncChatSessions } from '../api/chat'
import { useAccountStore } from '../stores/account'

let syncTimer: ReturnType<typeof setInterval> | null = null
let syncing = false
let refCount = 0

async function runSync(): Promise<void> {
  if (syncing) return
  const accountStore = useAccountStore()
  if (!accountStore.accounts.length) {
    try {
      await accountStore.loadAccounts()
    } catch {
      return
    }
  }
  if (!accountStore.accounts.length) return
  syncing = true
  try {
    await syncChatSessions()
    window.dispatchEvent(new CustomEvent('xy-sessions-synced', { detail: { at: Date.now() } }))
  } catch {
    /* 后台静默，避免打扰 */
  } finally {
    syncing = false
  }
}

export function useGlobalSessionSync(intervalMs = 45000): void {
  onMounted(() => {
    refCount += 1
    if (refCount === 1) {
      void runSync()
      syncTimer = setInterval(() => void runSync(), intervalMs)
    }
  })
  onBeforeUnmount(() => {
    refCount = Math.max(0, refCount - 1)
    if (refCount === 0 && syncTimer) {
      clearInterval(syncTimer)
      syncTimer = null
    }
  })
}
