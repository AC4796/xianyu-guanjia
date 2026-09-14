import { request, requestForm, apiBase } from './http'

export interface OrderRow {
  order_id?: string
  id?: string
  cookie_id?: string
  buyer_name?: string
  item_title?: string
  price?: string | number
  status?: string
  created_at?: string
  [key: string]: unknown
}

export async function getOrders(params: {
  cookie_id?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<{ data: OrderRow[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams()
  if (params.cookie_id) q.set('cookie_id', params.cookie_id)
  if (params.status && params.status !== 'all') q.set('status', params.status)
  q.set('page', String(params.page || 1))
  q.set('page_size', String(params.page_size || 20))
  const res = await request<{
    orders?: OrderRow[]
    data?: OrderRow[]
    total?: number
    page?: number
    page_size?: number
  }>(`/api/orders?${q.toString()}`)
  const data = res.orders || res.data || []
  return {
    data,
    total: typeof res.total === 'number' ? res.total : data.length,
    page: res.page || params.page || 1,
    page_size: res.page_size || params.page_size || 20
  }
}

export async function syncOrders(cookieId?: string, status?: string): Promise<any> {
  const form = new FormData()
  if (cookieId) form.append('cookie_id', cookieId)
  if (status) form.append('status', status)
  return requestForm('/api/orders/refresh', form)
}

/** 从闲鱼拉取卖家订单列表入库 */
export async function pullOrders(cookieId?: string, status?: string): Promise<any> {
  const form = new FormData()
  if (cookieId) form.append('cookie_id', cookieId)
  if (status && status !== 'all') form.append('status', status)
  return requestForm('/api/orders/pull', form)
}

export const manualShipOrder = (
  orderIds: string[],
  shipMode: string,
  content?: string
): Promise<{ success?: boolean; message?: string }> =>
  request('/api/orders/manual-ship', {
    method: 'POST',
    json: { order_ids: orderIds, ship_mode: shipMode, custom_content: content }
  })

export async function getOrderDetail(orderId: string): Promise<OrderRow | null> {
  const res = await request<{ success?: boolean; data?: OrderRow; order?: OrderRow }>(
    `/api/orders/${encodeURIComponent(orderId)}`
  )
  return res?.data || res?.order || null
}

export const deleteOrder = (orderId: string) =>
  request<{ success?: boolean; message?: string }>(`/api/orders/${encodeURIComponent(orderId)}`, {
    method: 'DELETE'
  })

export const refreshSingleOrder = (orderId: string) =>
  request<{ success?: boolean; message?: string }>(
    `/api/orders/${encodeURIComponent(orderId)}/refresh`,
    { method: 'POST', json: {} }
  )

export const adjustOrderPrice = (orderId: string, cookieId: string, price: number, postFee = 0) =>
  request(`/orders/${encodeURIComponent(orderId)}/adjust-price`, {
    method: 'POST',
    json: { cookie_id: cookieId, price, post_fee: postFee }
  })

export { apiBase }
