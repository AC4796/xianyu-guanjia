import { request } from './http'

export interface ItemRow {
  item_id?: string
  id?: string
  cookie_id?: string
  title?: string
  price?: string | number
  status?: string
  local_status?: string
  pic_url?: string
  [key: string]: unknown
}

export async function getItems(cookieId?: string): Promise<ItemRow[]> {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  const res = await request<{ items?: ItemRow[] } | ItemRow[]>(`/items${q}`)
  return Array.isArray(res) ? res : res.items || []
}

export const syncItemsFromAccount = (
  cookieId: string,
  opts?: { fast?: boolean; page_size?: number; page_delay?: number; skip_detail?: boolean }
) =>
  request('/items/get-all-from-account', {
    method: 'POST',
    json: {
      cookie_id: cookieId,
      fast: opts?.fast !== false,
      page_size: opts?.page_size ?? 50,
      page_delay: opts?.page_delay ?? 0.15,
      skip_detail: opts?.skip_detail !== false
    }
  })

export const updateItemLocalStatus = (cookieId: string, itemId: string, localStatus: 'on' | 'off') =>
  request(`/items/${cookieId}/${itemId}/local-status`, {
    method: 'PUT',
    json: { local_status: localStatus }
  })

export const polishItem = (cookieId: string, itemId: string) =>
  request(`/items/${cookieId}/${itemId}/polish`, { method: 'POST', json: {} })

export const deleteItem = (cookieId: string, itemId: string) =>
  request(`/items/${cookieId}/${itemId}`, { method: 'DELETE' })

export const searchItems = (
  keyword: string,
  page = 1,
  pageSize = 20,
  opts?: { min_want?: number | null; min_view?: number | null; cookie_id?: string | null }
) =>
  request<{
    success?: boolean
    data?: ItemRow[]
    items?: ItemRow[]
    total?: number
    error?: string
    has_more?: boolean
  }>('/items/search', {
    method: 'POST',
    json: {
      keyword,
      page,
      page_size: pageSize,
      min_want: opts?.min_want ?? undefined,
      min_view: opts?.min_view ?? undefined,
      cookie_id: opts?.cookie_id || undefined
    }
  })

/** 一次采集多页，返回全部结果，前端本地翻页 */
export const searchItemsBulk = (
  keyword: string,
  fetchCount: number,
  opts?: { min_want?: number | null; min_view?: number | null; cookie_id?: string | null }
) =>
  request<{
    success?: boolean
    data?: ItemRow[]
    total?: number
    error?: string
    total_pages?: number
    fetched_pages?: number
    source?: string
  }>('/items/search_multiple', {
    method: 'POST',
    timeoutMs: 165000,
    json: {
      keyword,
      fetch_count: fetchCount,
      total_pages: Math.max(1, Math.ceil(fetchCount / 30)),
      min_want: opts?.min_want ?? undefined,
      min_view: opts?.min_view ?? undefined,
      cookie_id: opts?.cookie_id || undefined
    }
  })

export const getPublishDetail = (cookieId: string, itemId: string) =>
  request<{ success?: boolean; data?: Record<string, unknown> }>(
    `/items/publish/detail?cookie_id=${encodeURIComponent(cookieId)}&item_id=${encodeURIComponent(itemId)}`
  )

export const getPublishDefaultLocation = (cookieId: string) =>
  request<{ success?: boolean; data?: Record<string, unknown> }>(
    `/items/publish/default-location?cookie_id=${encodeURIComponent(cookieId)}`
  )

export const recommendPublishCategory = (payload: {
  cookie_id: string
  title?: string
  desc?: string
  images?: Array<{ url: string; width?: number; height?: number } | string>
}) =>
  request<{
    success?: boolean
    data?: {
      options?: Array<{
        catId?: string
        catName?: string
        channelCatId?: string
        tbCatId?: string
        source?: string
      }>
      predict?: Record<string, string>
    }
  }>('/items/publish/recommend-category', { method: 'POST', json: payload })

export const uploadPublishImageBase64 = (cookieId: string, dataUrl: string) =>
  request<{ success?: boolean; data?: { url: string; width: number; height: number } }>(
    '/items/publish/upload-image-base64',
    { method: 'POST', json: { cookie_id: cookieId, data_url: dataUrl } }
  )

/** 采集/外链图转存到闲鱼 CDN */
export const transferPublishImage = (cookieId: string, url: string) =>
  request<{ success?: boolean; data?: { url: string; width: number; height: number } }>(
    '/items/publish/transfer-image',
    { method: 'POST', json: { cookie_id: cookieId, url } }
  )

export const publishItem = (payload: {
  cookie_id: string
  title: string
  desc?: string
  price: number
  original_price?: number
  quantity?: number
  images: Array<{ url: string; width?: number; height?: number } | string>
  shipping?: string
  post_price?: number
  can_self_pickup?: boolean
  location?: Record<string, unknown> | null
  category?: Record<string, unknown> | null
  schedule_at?: string | null
  dedup_text?: boolean
  crop_ratio?: number | null
}) =>
  request<{ success?: boolean; data?: { item_id?: string } }>('/items/publish', {
    method: 'POST',
    json: payload
  })

export const publishItemBatch = (payload: {
  cookie_id: string
  items: Array<Record<string, unknown>>
  interval_sec?: number
}) =>
  request<{ success?: boolean; results?: Array<{ ok: boolean; error?: string }> }>(
    '/items/publish/batch',
    { method: 'POST', json: payload }
  )

export const quickBuyItem = (payload: {
  cookie_id: string
  item_id: string
  pay_password?: string
}) =>
  request<{
    success?: boolean
    need_manual?: boolean
    url?: string
    message?: string
    filled_password?: boolean
  }>('/items/quick-buy', {
    method: 'POST',
    json: payload
  })

export const updateItemPrice = (cookieId: string, itemId: string, price: number, originalPrice?: number) =>
  request(`/items/${encodeURIComponent(cookieId)}/${encodeURIComponent(itemId)}/update-price`, {
    method: 'POST',
    json: { price, original_price: originalPrice }
  })

export const editItem = (payload: {
  cookie_id: string
  item_id: string
  title?: string
  desc?: string
  price?: number
  original_price?: number
}) =>
  request<{ success?: boolean; message?: string }>('/items/edit', {
    method: 'POST',
    json: payload
  })

export const getItemEditDetail = (cookieId: string, itemId: string) =>
  request<{
    success?: boolean
    data?: {
      item_id?: string
      title?: string
      desc?: string
      price?: number | null
      original_price?: number | null
      images?: string[]
      app_only?: boolean
      tip?: string
    }
  }>(
    // 勿用 /items/edit-detail：会被路由 /items/{cid} 抢成 cid=edit-detail →「无权限访问该Cookie」
    `/item/edit-detail?cookie_id=${encodeURIComponent(cookieId)}&item_id=${encodeURIComponent(itemId)}`
  )

export const batchUpdateItemPrice = (body: Record<string, unknown>) =>
  request<{ success?: boolean; message?: string; results?: any[] }>('/items/batch-update-price', {
    method: 'POST',
    json: body
  })
