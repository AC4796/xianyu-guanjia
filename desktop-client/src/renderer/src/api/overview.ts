import { request } from './http'

export interface AccountOverview {
  cookie_id: string
  nickname: string
  avatar_url: string
  online: boolean
  enabled: boolean
  health_reason?: string
  /** 需要扫码重新授权（风控/令牌失效） */
  need_reauth?: boolean
  /** 闲鱼官方原文转写后的提示 */
  official_message?: string
  /** none | reconnect | reauth */
  auth_action?: 'none' | 'reconnect' | 'reauth' | string
  item_count: number
  /** 宝贝浏览量合计（平台曝光近似） */
  exposure: number
  today_orders: number
  today_amount: number
  /** 今日取消/关闭订单数 */
  today_cancelled?: number
  session_count: number
  /** 对方最后发言、待你回复的会话数 */
  unread_sessions?: number
  /** 待付款 */
  pending_pay?: number
  /** 待发货 */
  pending_ship?: number
  /** 已发货待收货 */
  shipped?: number
  /** 退款中 */
  refunding?: number
  /** 待评价 */
  pending_review?: number
  auto_confirm?: boolean
  ai_enabled?: boolean
  daily_polish?: boolean
  auto_review?: boolean
}

export async function getAccountOverview(cookieId?: string): Promise<AccountOverview[]> {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  const res = await request<{ data?: AccountOverview[] } | AccountOverview[]>(
    `/api/account-overview${q}`
  )
  return Array.isArray(res) ? res : res.data || []
}

export const reconnectAccount = (cookieId: string, force = false) =>
  request<{ success?: boolean; message?: string; need_reauth?: boolean }>(
    `/cookies/${cookieId}/reconnect${force ? '?force=true' : ''}`,
    {
      method: 'POST',
      json: {}
    }
  )
