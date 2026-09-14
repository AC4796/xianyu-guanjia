import request from '@/utils/http'
import type { Account, AccountDetail, ApiResponse, AIReplySettings } from './types'

export const getAccounts = async (): Promise<Account[]> => {
  const ids: string[] = await request.get({ url: '/cookies' })
  return (ids || []).map((id) => ({
    id,
    cookie: '',
    enabled: true,
    use_ai_reply: false,
    use_default_reply: false,
    auto_confirm: false
  }))
}

export const getAccountDetails = async (): Promise<AccountDetail[]> => {
  const data = await request.get<
    Array<{
      id: string
      enabled: boolean
      auto_confirm: boolean
      remark?: string
      pause_duration?: number
      username?: string
      show_browser?: boolean
      nickname?: string
      tracknick?: string
      unb?: string
      avatar_url?: string
      chat_running?: boolean
      online?: boolean
    }>
  >({ url: '/cookies/details' })

  return (data || []).map((item) => ({
    id: item.id,
    cookie: '',
    value: '',
    enabled: item.enabled,
    auto_confirm: item.auto_confirm,
    remark: item.remark,
    note: item.remark,
    pause_duration: item.pause_duration,
    username: item.username || '',
    login_password: '',
    show_browser: item.show_browser,
    nickname: item.nickname || item.tracknick || item.remark || item.id,
    avatar_url:
      item.avatar_url ||
      (item.unb || item.id
        ? `https://api.dicebear.com/7.x/avataaars/svg?seed=${item.unb || item.id}`
        : ''),
    ai_enabled: false,
    use_ai_reply: false,
    use_default_reply: false,
    chat_running: item.chat_running,
    online: item.online,
    unb: item.unb,
    tracknick: item.tracknick,
    health_status: (item as any).health_status || (item.online ? 'normal' : 'abnormal'),
    health_reason: (item as any).health_reason || '',
    last_risk_at: (item as any).last_risk_at
  })) as AccountDetail[]
}

export const addAccount = (data: { id: string; cookie: string }) =>
  request.post<ApiResponse>({ url: '/cookies', data: { id: data.id, value: data.cookie } })

export const updateAccountCookie = (id: string, value: string) =>
  request.put({ url: `/cookies/${id}`, data: { id, value } })

export const updateAccountStatus = (id: string, enabled: boolean) =>
  request.put({ url: `/cookies/${id}/status`, data: { enabled } })

export const updateAccountRemark = (id: string, remark: string) =>
  request.put({ url: `/cookies/${id}/remark`, data: { remark } })

export const updateAccountAutoConfirm = (id: string, autoConfirm: boolean) =>
  request.put({ url: `/cookies/${id}/auto-confirm`, data: { auto_confirm: autoConfirm } })

export const updateAccountPauseDuration = (id: string, pauseDuration: number) =>
  request.put({ url: `/cookies/${id}/pause-duration`, data: { pause_duration: pauseDuration } })

export const refreshAccountProfile = (id: string) =>
  request.post<{
    success: boolean
    message?: string
    nickname?: string
    avatar_url?: string
  }>({ url: `/cookies/${id}/refresh-profile` })

export const reconnectAccount = (id: string) =>
  request.post<{ success: boolean; message?: string }>({ url: `/cookies/${id}/reconnect` })

export const updateAccountLoginInfo = (
  id: string,
  data: { username?: string; login_password?: string; show_browser?: boolean }
) => request.put({ url: `/cookies/${id}/login-info`, data })

export const deleteAccount = (id: string) => request.del({ url: `/cookies/${id}` })

export const generateQRLogin = () =>
  request.post<{ success: boolean; session_id?: string; qr_code_url?: string }>({
    url: '/qr-login/generate'
  })

export const checkQRLoginStatus = (sessionId: string) =>
  request.get({ url: `/qr-login/check/${sessionId}` })

export const passwordLogin = (data: {
  account_id?: string
  account: string
  password: string
  show_browser?: boolean
}) => request.post({ url: '/password-login', data })

export const checkPasswordLoginStatus = (sessionId: string) =>
  request.get({ url: `/password-login/check/${sessionId}` })

export const getAllAISettings = () =>
  request.get<Record<string, AIReplySettings>>({ url: '/ai-reply-settings' })

export const getAIReplySettings = (cookieId: string) =>
  request.get<AIReplySettings>({ url: `/ai-reply-settings/${cookieId}` })

export const updateAIReplySettings = (cookieId: string, settings: Partial<AIReplySettings>) =>
  request.put({
    url: `/ai-reply-settings/${cookieId}`,
    data: {
      ai_enabled: settings.ai_enabled ?? false,
      model_name: settings.model_name ?? 'qwen-plus',
      api_key: settings.api_key ?? '',
      base_url: settings.base_url ?? 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      max_discount_percent: settings.max_discount_percent ?? 10,
      max_discount_amount: settings.max_discount_amount ?? 100,
      max_bargain_rounds: settings.max_bargain_rounds ?? 3,
      custom_prompts: settings.custom_prompts ?? ''
    }
  })

export const testAIConnection = async (cookieId: string): Promise<ApiResponse> => {
  const result = await request.post<{ success?: boolean; message?: string; reply?: string }>({
    url: `/ai-reply-test/${cookieId}`,
    data: { message: '你好，这是一条测试消息' }
  })
  if (result.reply) return { success: true, message: `AI 回复: ${result.reply}` }
  return { success: result.success ?? true, message: result.message || 'AI 连接测试成功' }
}
