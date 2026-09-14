import { request } from './http'

export interface AutomationSettings {
  cookie_id: string
  auto_confirm: boolean
  auto_delivery: boolean
  unpaid_repricing: boolean
  unpaid_target_price: number
  unpaid_markup_type?: 'percent' | 'amount'
  unpaid_markup_value?: number
  /** 拍下后延迟改价秒数，默认 30 */
  unpaid_repricing_delay_sec?: number
  gift_after_review: boolean
  request_review: boolean
  request_review_hours: number
  request_review_text: string
  auto_review: boolean
  auto_review_text: string
  daily_polish: boolean
  daily_polish_time: string
  last_polish_date?: string
  dropship_pay_password?: string
}

export interface AIReplySettings {
  ai_enabled: boolean
  model_name: string
  api_key: string
  base_url: string
  max_discount_percent: number
  max_discount_amount: number
  max_bargain_rounds: number
  custom_prompts: string
  auto_apply_quote?: boolean
}

export async function getAutomationSettings(cookieId: string): Promise<AutomationSettings> {
  const res = await request<{ data?: AutomationSettings } | AutomationSettings>(
    `/automation-settings/${encodeURIComponent(cookieId)}`
  )
  return (res as any).data || (res as AutomationSettings)
}

export const updateAutomationSettings = (cookieId: string, data: Partial<AutomationSettings>) =>
  request(`/automation-settings/${encodeURIComponent(cookieId)}`, {
    method: 'PUT',
    json: data
  })

export async function getAIReplySettings(cookieId: string): Promise<AIReplySettings> {
  return request(`/ai-reply-settings/${encodeURIComponent(cookieId)}`)
}

export const updateAIReplySettings = (cookieId: string, data: Partial<AIReplySettings>) =>
  request(`/ai-reply-settings/${encodeURIComponent(cookieId)}`, {
    method: 'PUT',
    json: data
  })

export const testAIConnection = (cookieId: string, message = '你好，能便宜点吗？') =>
  request(`/ai-reply-test/${encodeURIComponent(cookieId)}`, {
    method: 'POST',
    json: { message }
  })
