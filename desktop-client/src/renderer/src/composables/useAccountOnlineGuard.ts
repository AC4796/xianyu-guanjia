/** 后台保活：离线账号自动重连，保证发消息不用临时等待 */
import { onBeforeUnmount, onMounted } from 'vue'
import { reconnectAccount } from '../api/accounts'
import { useAccountStore } from '../stores/account'

let timer: ReturnType<typeof setInterval> | null = null
let refCount = 0
let busy = false
const lastTry: Record<string, number> = {}

async function tick(): Promise<void> {
  if (busy) return
  const store = useAccountStore()
  try {
    await store.loadAccounts()
  } catch {
    return
  }
  const offline = store.accounts.filter((a) => a.enabled !== false && !a.online)
  if (!offline.length) return
  busy = true
  try {
    const now = Date.now()
    for (const a of offline.slice(0, 3)) {
      if (lastTry[a.id] && now - lastTry[a.id] < 60000) continue
      lastTry[a.id] = now
      try {
        await reconnectAccount(a.id)
      } catch {
        /* 静默 */
      }
    }
    await new Promise((r) => setTimeout(r, 4000))
    await store.loadAccounts()
  } finally {
    busy = false
  }
}

export function useAccountOnlineGuard(intervalMs = 30000): void {
  onMounted(() => {
    refCount += 1
    if (refCount === 1) {
      void tick()
      timer = setInterval(() => void tick(), intervalMs)
    }
  })
  onBeforeUnmount(() => {
    refCount = Math.max(0, refCount - 1)
    if (refCount === 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  })
}
