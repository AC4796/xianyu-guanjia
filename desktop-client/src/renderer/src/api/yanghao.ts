import { request } from './http'

export interface YanghaoRecord {
  item_id?: string
  title?: string
  price?: string | number
  original_price?: string | number
  pic_url?: string
  seller_id?: string
  seller_nick?: string
  want_num?: string | number
  view_count?: string | number
  browse_status?: string
  msg_status?: string
  msg_detail?: string
  round?: number
  ts?: string
  web_url?: string
  area?: string
}

export interface YanghaoStatus {
  status?: string
  keyword?: string
  target_count?: number
  dwell_sec?: number
  leave_msg?: boolean
  message_text?: string
  loop_times?: number
  browsed?: number
  messaged?: number
  msg_failed?: number
  browse_failed?: number
  logs?: string[]
  records?: YanghaoRecord[]
  progress?: string
  today?: { date?: string; count?: number }
}

export const getYanghaoStatus = (cookieId: string) =>
  request<{ success?: boolean; data?: YanghaoStatus }>(
    `/yanghao/status?cookie_id=${encodeURIComponent(cookieId)}`
  )

export const startYanghao = (body: Record<string, unknown>) =>
  request<{ success?: boolean; data?: YanghaoStatus; message?: string }>('/yanghao/start', {
    method: 'POST',
    json: body
  })

export const pauseYanghao = (cookieId: string) =>
  request('/yanghao/pause', { method: 'POST', json: { cookie_id: cookieId } })

export const resumeYanghao = (cookieId: string, form?: Record<string, unknown>) =>
  request('/yanghao/resume', {
    method: 'POST',
    json: { cookie_id: cookieId, ...(form || {}) }
  })

export const stopYanghao = (cookieId: string) =>
  request('/yanghao/stop', { method: 'POST', json: { cookie_id: cookieId } })
