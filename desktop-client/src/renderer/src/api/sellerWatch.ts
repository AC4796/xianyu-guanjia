import { request } from './http'

export interface SellerWatch {
  id: number
  cookie_id: string
  seller_user_id: string
  seller_nick?: string
  seller_avatar?: string
  enabled?: number | boolean
  follow_price?: number | boolean
  auto_detect_new?: number | boolean
  markup_type?: string
  markup_value?: number
  interval_sec?: number
  last_sync_at?: string
  remote_item_count?: number
  item_count?: number
  remark?: string
}

export interface SellerWatchItem {
  id: number
  watch_id: number
  cookie_id: string
  source_item_id: string
  local_item_id?: string
  source_title?: string
  last_source_price?: string
  last_local_price?: string
  status?: string
  dropship?: number | boolean
}

export const listSellerWatches = (cookieId?: string) => {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  return request<{ success?: boolean; data?: SellerWatch[] }>(`/seller-watch${q}`)
}

export const upsertSellerWatch = (
  body: Partial<SellerWatch> & {
    cookie_id: string
    seller_user_id: string
    seller_avatar?: string
    avatar_url?: string
  }
) => request<{ success?: boolean; data?: SellerWatch }>('/seller-watch', { method: 'POST', json: body })

export const deleteSellerWatch = (watchId: number) =>
  request(`/seller-watch/${watchId}`, { method: 'DELETE' })

export const batchDeleteSellerWatches = (ids: number[]) =>
  request<{ success?: boolean; deleted?: number }>('/seller-watch/batch-delete', {
    method: 'POST',
    json: { ids }
  })

export const listWatchItems = (watchId: number, page = 1, pageSize = 20) =>
  request<{
    success?: boolean
    data?: SellerWatchItem[]
    total?: number
    page?: number
    page_size?: number
    watch?: SellerWatch
  }>(`/seller-watch/${watchId}/items?page=${page}&page_size=${pageSize}`)

export const bindWatchItem = (
  watchId: number,
  body: {
    source_item_id: string
    local_item_id: string
    source_title?: string
    last_source_price?: string
    dropship?: boolean | number
  }
) => request(`/seller-watch/${watchId}/bind`, { method: 'POST', json: body })

export const listDropshipJobs = (cookieId?: string) => {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  return request<{ success?: boolean; data?: any[] }>(`/dropship-jobs${q}`)
}

export const retryDropshipBuy = (jobId: number, payPassword?: string) =>
  request(`/dropship-jobs/${jobId}/retry-buy`, {
    method: 'POST',
    json: { pay_password: payPassword || '' }
  })

export const syncSellerWatch = (watchId: number) =>
  request<{
    success?: boolean
    message?: string
    new_items?: unknown[]
    price_updates?: unknown[]
    downshelved?: unknown[]
  }>(`/seller-watch/${watchId}/sync`, { method: 'POST', json: {} })

export const listRemoteSellerItems = (watchId: number, page = 1) =>
  request<{
    success?: boolean
    items?: any[]
    next_page?: boolean
    total_count?: number
    seller_avatar?: string
    seller_nick?: string
    watch?: SellerWatch
    message?: string
  }>(`/seller-watch/${watchId}/remote-items?page=${page}`)

export const previewSellerItems = (cookieId: string, sellerUserId: string, page = 1) =>
  request<{
    success?: boolean
    items?: any[]
    next_page?: boolean
    total_count?: number
    seller_avatar?: string
    seller_nick?: string
    message?: string
  }>(
    `/seller-watch/preview-items?cookie_id=${encodeURIComponent(cookieId)}&seller_user_id=${encodeURIComponent(sellerUserId)}&page=${page}`
  )

export const resolveSellerInput = (cookieId: string, raw: string, deep = false) =>
  request<{
    success?: boolean
    seller_user_id?: string
    item_id?: string
    cleaned_url?: string
    need_manual_seller_link?: boolean
    item?: { item_id?: string; title?: string; price?: string; seller_nick?: string }
    profile?: {
      success?: boolean
      nickname?: string
      avatar_url?: string
      user_id?: string
      bio?: string
      sold_count?: string
      good_rate?: string
      register_days?: string
      city?: string
      message?: string
    }
    message?: string
  }>('/seller-watch/resolve', {
    method: 'POST',
    json: { cookie_id: cookieId, raw, deep },
    signal: AbortSignal.timeout(deep ? 180000 : 30000)
  })
