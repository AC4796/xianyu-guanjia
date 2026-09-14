<template>
  <div class="art-full-height p-4 online-chat-page">
    <div class="art-card chat-shell">
      <div class="chat-sidebar">
        <div class="sidebar-head">
          <span class="font-medium">在线聊天</span>
          <ElTag :type="wsOk ? 'success' : 'info'" size="small" effect="light">
            {{ wsOk ? '实时推送中' : '连接中…' }}
          </ElTag>
        </div>

        <ElTabs v-model="activeCookieId" class="account-tabs" @tab-change="onAccountTab">
          <ElTabPane
            v-for="a in accounts"
            :key="a.id"
            :name="a.id"
            :label="a.nickname || a.remark || a.id"
          >
            <template #label>
              <div class="tab-label">
                <ElAvatar :size="20" :src="a.avatar_url" />
                <span class="truncate">{{ a.nickname || a.remark || a.id }}</span>
                <ElBadge
                  v-if="chatUnread.byCookie[a.id]"
                  :value="chatUnread.byCookie[a.id]"
                  :max="99"
                  class="tab-badge"
                />
              </div>
            </template>
          </ElTabPane>
        </ElTabs>

        <div class="flex items-center gap-2 mb-3">
          <ElInput v-model="keyword" clearable placeholder="搜索买家/商品" class="flex-1" />
          <ElButton size="small" :loading="syncing" @click="doSync">同步</ElButton>
        </div>

        <div class="session-list" v-loading="loadingSessions">
          <div
            v-for="s in filteredSessions"
            :key="`${s.cookie_id}-${s.chat_id}`"
            class="session-item"
            :class="{ active: isActive(s) }"
            @click="selectSession(s)"
          >
            <div class="session-avatar-wrap">
              <ElAvatar :size="42" :src="buyerAvatar(s)" />
              <span v-if="sessionUnread(s)" class="session-dot">{{ sessionUnread(s) }}</span>
            </div>
            <div class="session-main min-w-0">
              <div class="flex justify-between gap-2">
                <span class="font-medium truncate">{{ s.buyer_nick || s.buyer_id || '未知买家' }}</span>
                <span class="text-xs text-g-400 shrink-0">{{ formatTime(s.ts) }}</span>
              </div>
              <div class="text-xs text-g-500 truncate mt-0.5">
                {{ s.item_title || s.content || '—' }}
              </div>
            </div>
          </div>
          <ElEmpty
            v-if="!loadingSessions && !filteredSessions.length"
            :description="
              activeCookieId
                ? '该账号暂无会话，可点同步或等待买家消息'
                : '请先添加账号'
            "
          />
        </div>
      </div>

      <div class="chat-main">
        <template v-if="current">
          <div class="chat-head">
            <div class="flex items-center gap-3 min-w-0">
              <ElAvatar :size="40" :src="buyerAvatar(current)" />
              <div class="min-w-0">
                <div class="font-semibold truncate">{{ current.buyer_nick || current.buyer_id }}</div>
                <div class="text-xs text-g-500 truncate">
                  账号 {{ current.account_nickname || current.cookie_id }} · 会话 {{ current.chat_id }}
                </div>
              </div>
            </div>
            <ElButton size="small" :loading="loadingMsgs" @click="() => loadMessages(true)">
              拉取最新
            </ElButton>
          </div>

          <div v-if="current.item_id" class="item-card">
            <img v-if="current.item_pic" :src="current.item_pic" class="item-pic" alt="" />
            <div class="min-w-0 flex-1">
              <a
                class="font-medium truncate block text-primary hover:underline"
                :href="`https://www.goofish.com/item?id=${current.item_id}`"
                target="_blank"
                rel="noopener"
                >{{ current.item_title || `商品 ${current.item_id}` }}</a
              >
              <div class="text-sm text-orange-600 mt-1" v-if="current.item_price">¥ {{ current.item_price }}</div>
              <div class="text-xs text-g-400 mt-1">ID: {{ current.item_id }}</div>
            </div>
          </div>

          <div ref="msgBoxRef" class="msg-box" v-loading="loadingMsgs">
            <div
              v-for="(m, idx) in messages"
              :key="`${m.ts}-${idx}-${m.content}`"
              class="msg-row"
              :class="m.direction === 'out' ? 'mine' : 'theirs'"
            >
              <ElAvatar v-if="m.direction !== 'out'" :size="32" :src="buyerAvatar(m)" />
              <div class="bubble">
                <div class="bubble-meta">{{ formatTime(m.ts) }}</div>
                <img v-if="m.content_pic" :src="m.content_pic" class="bubble-img" alt="图片消息" />
                <div v-else class="bubble-text">{{ m.content }}</div>
                <div v-if="m.item_title || m.item_pic" class="bubble-item">
                  <img v-if="m.item_pic" :src="m.item_pic" alt="" />
                  <div>
                    <a
                      v-if="m.item_id"
                      class="truncate block hover:underline"
                      :href="`https://www.goofish.com/item?id=${m.item_id}`"
                      target="_blank"
                      rel="noopener"
                      >{{ m.item_title }}</a
                    >
                    <div v-else class="truncate">{{ m.item_title }}</div>
                    <div v-if="m.item_price" class="price">¥ {{ m.item_price }}</div>
                  </div>
                </div>
                <div v-if="m.direction === 'out'" class="read-status" :class="readClass(m)">
                  <span class="checks">{{ readLabel(m) }}</span>
                </div>
              </div>
              <ElAvatar v-if="m.direction === 'out'" :size="32" :src="myAvatar(m)" />
            </div>
          </div>

          <div class="composer">
            <ElInput
              v-model="draft"
              type="textarea"
              :rows="2"
              placeholder="输入回复内容，Enter 发送（Shift+Enter 换行）"
              @keydown.enter.exact.prevent="doSend"
            />
            <ElButton type="primary" :loading="sending" :disabled="!draft.trim()" @click="doSend">
              发送
            </ElButton>
          </div>
        </template>
        <div v-else class="empty-main">
          <ElEmpty description="选择左侧会话开始聊天（本地消息秒开，需要最新历史再点「拉取最新」）" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    getAccountDetails,
    getChatSessions,
    getChatMessages,
    sendChatMessage,
    syncChatSessions,
    buildChatWsUrl,
    type AccountDetail,
    type ChatMessage
  } from '@/api/xy'
  import { ElMessage } from 'element-plus'
  import { useChatUnreadStore } from '@/store/modules/chatUnread'
  import { useRoute } from 'vue-router'

  defineOptions({ name: 'OnlineChat' })

  const chatUnread = useChatUnreadStore()

  function msgKey(m: Partial<ChatMessage>) {
    return `${m.cookie_id || ''}|${m.chat_id || ''}|${m.direction || ''}|${(m.content || '').trim()}|${m.ts || ''}`
  }

  function pushMessageDedupe(m: ChatMessage) {
    const key = msgKey(m)
    const exists = messages.value.some((x) => {
      if (msgKey(x) === key) return true
      // 宽松：同会话同方向同内容，时间差 < 8s
      return (
        x.cookie_id === m.cookie_id &&
        x.chat_id === m.chat_id &&
        x.direction === m.direction &&
        (x.content || '').trim() === (m.content || '').trim() &&
        Math.abs(Number(x.ts || 0) - Number(m.ts || 0)) < 8000
      )
    })
    if (!exists) messages.value.push(m)
  }

  const accounts = ref<AccountDetail[]>([])
  const activeCookieId = ref('')
  const loadingSessions = ref(false)
  const loadingMsgs = ref(false)
  const sending = ref(false)
  const syncing = ref(false)
  const sessions = ref<ChatMessage[]>([])
  const messages = ref<ChatMessage[]>([])
  const current = ref<ChatMessage | null>(null)
  const draft = ref('')
  const keyword = ref('')
  const wsOk = ref(false)
  const msgBoxRef = ref<HTMLElement | null>(null)
  const unreadMap = reactive<Record<string, number>>({})

  function sessionUnread(s: ChatMessage) {
    const sk = chatUnread.sessionKey(s.cookie_id, s.chat_id)
    return chatUnread.bySession[sk] || 0
  }

  function myAvatar(m?: ChatMessage) {
    const cid = m?.cookie_id || current.value?.cookie_id || activeCookieId.value
    const a = accounts.value.find((x) => x.id === cid)
    return a?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${cid || 'me'}`
  }

  /** 已读启发式：对方在本会话后续有消息进来 → 之前自己发的视为已读 */
  function isMsgRead(m: ChatMessage) {
    if ((m as any).read === true || (m as any).read_status === 'read') return true
    if (m.direction !== 'out') return false
    const idx = messages.value.findIndex((x) => x === m)
    if (idx < 0) return false
    return messages.value.slice(idx + 1).some((x) => x.direction === 'in')
  }

  function readLabel(m: ChatMessage) {
    return isMsgRead(m) ? '已读' : '未读'
  }

  function readClass(m: ChatMessage) {
    return isMsgRead(m) ? 'is-read' : 'is-unread'
  }

  let ws: WebSocket | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  const filteredSessions = computed(() => {
    const cid = activeCookieId.value
    const base = sessions.value.filter((s) => !cid || s.cookie_id === cid)
    const q = keyword.value.trim().toLowerCase()
    if (!q) return base
    return base.filter((s) =>
      [s.buyer_nick, s.buyer_id, s.item_title, s.content]
        .filter(Boolean)
        .some((x) => String(x).toLowerCase().includes(q))
    )
  })

  function buyerAvatar(s: Partial<ChatMessage>) {
    if (s.buyer_avatar) return s.buyer_avatar
    const seed = s.buyer_id || s.chat_id || 'user'
    return `https://api.dicebear.com/7.x/avataaars/svg?seed=${seed}`
  }

  function formatTime(ts?: number) {
    if (!ts) return ''
    const d = new Date(ts > 1e12 ? ts : ts * 1000)
    const now = new Date()
    const sameDay = d.toDateString() === now.toDateString()
    const hm = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    if (sameDay) return hm
    return `${d.getMonth() + 1}/${d.getDate()} ${hm}`
  }

  function isActive(s: ChatMessage) {
    return current.value?.cookie_id === s.cookie_id && current.value?.chat_id === s.chat_id
  }

  function upsertSession(msg: ChatMessage) {
    const idx = sessions.value.findIndex(
      (s) => s.cookie_id === msg.cookie_id && s.chat_id === msg.chat_id
    )
    const next = {
      ...msg,
      account_nickname: msg.account_nickname || sessions.value[idx]?.account_nickname
    }
    if (idx >= 0) sessions.value.splice(idx, 1)
    sessions.value.unshift(next)
  }

  async function loadAccounts() {
    accounts.value = await getAccountDetails()
    if (!activeCookieId.value && accounts.value.length) {
      activeCookieId.value = accounts.value[0].id
    }
  }

  async function loadSessions() {
    if (!activeCookieId.value) {
      sessions.value = []
      return
    }
    loadingSessions.value = true
    try {
      sessions.value = await getChatSessions(activeCookieId.value)
    } finally {
      loadingSessions.value = false
    }
  }

  async function onAccountTab() {
    current.value = null
    messages.value = []
    draft.value = ''
    // 切到该账号时不同时清空未读，点开会话再清
    unreadMap[activeCookieId.value] = chatUnread.byCookie[activeCookieId.value] || 0
    await loadSessions()
  }

  async function doSync() {
    if (!activeCookieId.value) return
    syncing.value = true
    try {
      const res = await syncChatSessions(activeCookieId.value)
      ElMessage.success(`已同步 ${res?.saved ?? 0} 条会话`)
      await loadSessions()
    } catch (e: any) {
      ElMessage.error(e?.message || '同步失败')
    } finally {
      syncing.value = false
    }
  }

  async function selectSession(s: ChatMessage) {
    current.value = s
    chatUnread.clearSession(s.cookie_id, s.chat_id)
    if (s.cookie_id && unreadMap[s.cookie_id]) {
      unreadMap[s.cookie_id] = Math.max(0, (unreadMap[s.cookie_id] || 1) - 1)
    }
    draft.value = ''
    // 先本地秒开，不强制拉 WS 历史
    await loadMessages(false)
  }

  async function loadMessages(withSync = false) {
    if (!current.value) return
    loadingMsgs.value = true
    try {
      messages.value = await getChatMessages(
        current.value.cookie_id,
        current.value.chat_id,
        80,
        withSync
      )
      const withBuyer = [...messages.value].reverse().find((m) => m.buyer_id)
      if (withBuyer && current.value) {
        current.value = {
          ...current.value,
          buyer_id: withBuyer.buyer_id || current.value.buyer_id,
          buyer_nick: withBuyer.buyer_nick || current.value.buyer_nick,
          buyer_avatar: withBuyer.buyer_avatar || current.value.buyer_avatar,
          item_id: withBuyer.item_id || current.value.item_id,
          item_title: withBuyer.item_title || current.value.item_title,
          item_price: withBuyer.item_price || current.value.item_price,
          item_pic: withBuyer.item_pic || current.value.item_pic
        }
      }
      await nextTick()
      scrollBottom()
    } finally {
      loadingMsgs.value = false
    }
  }

  function scrollBottom() {
    const el = msgBoxRef.value
    if (el) el.scrollTop = el.scrollHeight
  }

  async function doSend() {
    if (!current.value || !draft.value.trim()) return
    if (!current.value.buyer_id) {
      ElMessage.warning('缺少对方用户 ID，暂无法发送（等对方再发一条后自动补齐）')
      return
    }
    sending.value = true
    try {
      const res = await sendChatMessage({
        cookie_id: current.value.cookie_id,
        chat_id: current.value.chat_id,
        to_user_id: current.value.buyer_id,
        message: draft.value.trim()
      })
      if (res?.success === false) {
        ElMessage.error(res.message || '发送失败')
        return
      }
      draft.value = ''
      // 不本地插入：等待 /chat/send 的 WS 推送统一入列，避免重复
      // 若 1.5s 内 WS 未到，再回退拉本地
      const expectContent = (res?.data?.content || '').trim()
      setTimeout(async () => {
        if (!expectContent) {
          await loadMessages(false)
          return
        }
        const arrived = messages.value.some(
          (m) =>
            m.direction === 'out' &&
            (m.content || '').trim() === expectContent &&
            m.chat_id === current.value?.chat_id
        )
        if (!arrived && res?.data) {
          pushMessageDedupe(res.data)
          upsertSession({ ...current.value!, ...res.data })
          await nextTick()
          scrollBottom()
        }
      }, 1500)
    } catch (e: any) {
      ElMessage.error(e?.message || '发送失败')
    } finally {
      sending.value = false
    }
  }

  function onWsMessage(raw: string) {
    try {
      const data = JSON.parse(raw) as ChatMessage & { type?: string }
      if (data.type === 'pong' || data.type === 'connected') {
        wsOk.value = true
        return
      }
      if (data.type !== 'chat_message' && !data.chat_id) return

      // 非当前账号标签：计入未读，仍写入 sessions 缓存
      if (data.cookie_id && data.cookie_id !== activeCookieId.value) {
        if (data.direction !== 'out') {
          unreadMap[data.cookie_id] = (unreadMap[data.cookie_id] || 0) + 1
          chatUnread.pushIncoming(data)
        }
        upsertSession(data)
        return
      }

      upsertSession(data)
      if (
        current.value &&
        current.value.cookie_id === data.cookie_id &&
        current.value.chat_id === data.chat_id
      ) {
        current.value = {
          ...current.value,
          buyer_nick: data.buyer_nick || current.value.buyer_nick,
          buyer_avatar: data.buyer_avatar || current.value.buyer_avatar,
          buyer_id: data.buyer_id || current.value.buyer_id,
          item_id: data.item_id || current.value.item_id,
          item_title: data.item_title || current.value.item_title,
          item_price: data.item_price || current.value.item_price,
          item_pic: data.item_pic || current.value.item_pic
        }
        pushMessageDedupe(data)
        if (data.direction !== 'out') {
          chatUnread.clearSession(data.cookie_id, data.chat_id)
        }
        nextTick().then(scrollBottom)
      } else if (data.direction !== 'out') {
        unreadMap[data.cookie_id] = (unreadMap[data.cookie_id] || 0) + 1
        chatUnread.pushIncoming(data)
      }
    } catch {
      /* ignore */
    }
  }

  function connectWs() {
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
    ws = new WebSocket(buildChatWsUrl())
    ws.onopen = () => {
      wsOk.value = true
      if (pingTimer) clearInterval(pingTimer)
      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
      }, 25000)
    }
    ws.onmessage = (ev) => onWsMessage(String(ev.data || ''))
    ws.onclose = () => {
      wsOk.value = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(connectWs, 3000)
    }
    ws.onerror = () => {
      wsOk.value = false
    }
  }

  onMounted(async () => {
    await loadAccounts()
    // 从通知跳转：?cookie_id=&chat_id=
    const route = useRoute()
    const qCookie = String(route.query.cookie_id || '')
    const qChat = String(route.query.chat_id || '')
    if (qCookie && accounts.value.some((a) => a.id === qCookie)) {
      activeCookieId.value = qCookie
    }
    await loadSessions()
    if (qCookie && qChat) {
      const hit = sessions.value.find((s) => s.cookie_id === qCookie && s.chat_id === qChat)
      if (hit) await selectSession(hit)
    }
    if (activeCookieId.value && !sessions.value.length) {
      try {
        await syncChatSessions(activeCookieId.value)
        await loadSessions()
        if (qCookie && qChat) {
          const hit = sessions.value.find((s) => s.cookie_id === qCookie && s.chat_id === qChat)
          if (hit) await selectSession(hit)
        }
      } catch {
        /* ignore */
      }
    }
    // 同步账号角标
    Object.keys(chatUnread.byCookie).forEach((cid) => {
      unreadMap[cid] = chatUnread.byCookie[cid] || 0
    })
    connectWs()
  })

  onBeforeUnmount(() => {
    if (pingTimer) clearInterval(pingTimer)
    if (reconnectTimer) clearTimeout(reconnectTimer)
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
  })
</script>

<style scoped lang="scss">
  .online-chat-page {
    min-height: 0;
  }

  .chat-shell {
    display: flex;
    height: calc(100vh - 140px);
    min-height: 520px;
    overflow: hidden;
    padding: 0;
  }

  .chat-sidebar {
    width: 360px;
    border-right: 1px solid var(--el-border-color-lighter);
    display: flex;
    flex-direction: column;
    padding: 14px;
  }

  .sidebar-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .account-tabs {
    :deep(.el-tabs__header) {
      margin-bottom: 8px;
    }

    :deep(.el-tabs__content) {
      display: none;
    }
  }

  .tab-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    max-width: 120px;
  }

  .tab-badge {
    margin-left: 2px;
  }

  .session-list {
    flex: 1;
    overflow: auto;
  }

  .session-item {
    display: flex;
    gap: 10px;
    padding: 10px;
    border-radius: 10px;
    cursor: pointer;
    margin-bottom: 4px;

    &:hover,
    &.active {
      background: var(--el-fill-color-light);
    }
  }

  .session-avatar-wrap {
    position: relative;
    flex-shrink: 0;
  }

  .session-dot {
    position: absolute;
    top: -4px;
    right: -6px;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: 999px;
    background: var(--el-color-danger);
    color: #fff;
    font-size: 10px;
    line-height: 16px;
    text-align: center;
  }

  .session-main {
    flex: 1;
  }

  .chat-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .chat-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .item-card {
    display: flex;
    gap: 12px;
    margin: 12px 16px 0;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--el-fill-color-lighter);
  }

  .item-pic {
    width: 56px;
    height: 56px;
    object-fit: cover;
    border-radius: 8px;
    flex-shrink: 0;
  }

  .msg-box {
    flex: 1;
    overflow: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .msg-row {
    display: flex;
    gap: 8px;
    max-width: 78%;

    &.mine {
      align-self: flex-end;
      flex-direction: row-reverse;

      .bubble {
        background: var(--el-color-primary);
        color: #fff;

        .bubble-meta {
          color: rgba(255, 255, 255, 0.75);
        }

        .bubble-item {
          background: rgba(255, 255, 255, 0.15);
        }
      }
    }

    &.theirs {
      align-self: flex-start;
    }
  }

  .bubble {
    background: var(--el-fill-color-light);
    border-radius: 12px;
    padding: 8px 12px;
  }

  .read-status {
    margin-top: 4px;
    font-size: 11px;
    text-align: right;
    letter-spacing: 0.5px;

    .checks {
      opacity: 0.95;
    }

    &.is-read .checks {
      color: #67c23a;
    }

    &.is-unread .checks {
      color: rgba(255, 255, 255, 0.85);
    }
  }

  .msg-row.theirs .read-status {
    display: none;
  }

  .bubble-meta {
    font-size: 11px;
    color: var(--el-text-color-secondary);
    margin-bottom: 4px;
  }

  .bubble-text {
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.5;
  }

  .bubble-img {
    max-width: 220px;
    border-radius: 8px;
  }

  .bubble-item {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    padding: 6px;
    border-radius: 8px;
    background: var(--el-fill-color);

    img {
      width: 40px;
      height: 40px;
      object-fit: cover;
      border-radius: 6px;
    }

    .price {
      color: #ea580c;
      font-size: 12px;
    }
  }

  .composer {
    display: flex;
    gap: 10px;
    padding: 12px 16px;
    border-top: 1px solid var(--el-border-color-lighter);
    align-items: flex-end;
  }

  .empty-main {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
</style>
