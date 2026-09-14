import { onBeforeUnmount, onMounted, ref } from 'vue'
import { buildChatWsUrl } from '@/api/xy'
import { useChatUnreadStore } from '@/store/modules/chatUnread'
import { useRoute } from 'vue-router'

/** 全局聊天 WS：不在聊天页也能收红点 */
let sharedWs: WebSocket | null = null
let sharedRefCount = 0
let pingTimer: ReturnType<typeof setInterval> | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

function ensureSharedWs() {
  if (sharedWs && (sharedWs.readyState === WebSocket.OPEN || sharedWs.readyState === WebSocket.CONNECTING)) {
    return
  }
  const unread = useChatUnreadStore()
  const ws = new WebSocket(buildChatWsUrl())
  sharedWs = ws
  ws.onopen = () => {
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
  }
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(String(ev.data || ''))
      if (data.type === 'pong' || data.type === 'connected') return
      if (data.type !== 'chat_message' && !data.chat_id) return
      if (data.direction === 'out') return
      // 在聊天页时由页面自己处理未读；全局只在非聊天页累计，避免双计
      const path = window.location.pathname || ''
      if (path.includes('online-chat')) return
      unread.pushIncoming(data)
    } catch {
      /* ignore */
    }
  }
  ws.onclose = () => {
    sharedWs = null
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (sharedRefCount > 0) {
      reconnectTimer = setTimeout(ensureSharedWs, 3000)
    }
  }
}

export function useGlobalChatWs() {
  const connected = ref(false)
  onMounted(() => {
    sharedRefCount += 1
    ensureSharedWs()
    connected.value = true
  })
  onBeforeUnmount(() => {
    sharedRefCount = Math.max(0, sharedRefCount - 1)
    if (sharedRefCount === 0) {
      if (pingTimer) clearInterval(pingTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      try {
        sharedWs?.close()
      } catch {
        /* ignore */
      }
      sharedWs = null
    }
  })
  return { connected }
}

/** 供在线聊天页复用：判断当前是否在聊天路由 */
export function isOnOnlineChatRoute(route = useRoute()) {
  return String(route.path || '').includes('online-chat')
}
