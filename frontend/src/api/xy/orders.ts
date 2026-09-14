import request from '@/utils/http'
import type { Order, ApiResponse, PaginatedOrders, ShipMode, ManualShipResponse } from './types'

export const getOrders = async (
  cookieId?: string,
  status?: string,
  page = 1,
  pageSize = 20
): Promise<PaginatedOrders> => {
  const params: Record<string, string | number> = { page, page_size: pageSize }
  if (cookieId) params.cookie_id = cookieId
  if (status && status !== 'all') params.status = status

  const res = await request.get<{
    orders?: Order[]
    data?: Order[]
    total?: number
    page?: number
    page_size?: number
    total_pages?: number
  }>({ url: '/api/orders', params })

  const orders = res.orders || res.data || []
  return {
    success: true,
    data: orders,
    total: res.total || orders.length,
    page: res.page || page,
    page_size: res.page_size || pageSize,
    total_pages: res.total_pages || 1
  }
}

export const getOrderDetail = async (orderId: string) => {
  const result = await request.get<{ order?: Order; data?: Order }>({
    url: `/api/orders/${orderId}`
  })
  return { success: true, data: result.order || result.data }
}

export const updateOrder = (orderId: string, data: Partial<Order>) =>
  request.put<ApiResponse>({ url: `/api/orders/${orderId}`, data })

export const deleteOrder = (orderId: string) =>
  request.del<ApiResponse>({ url: `/api/orders/${orderId}` })

export const syncOrders = async (cookieId?: string, status?: string) => {
  const formData = new FormData()
  if (cookieId) formData.append('cookie_id', cookieId)
  if (status) formData.append('status', status)
  const response = await fetch('/api/orders/refresh', {
    method: 'POST',
    credentials: 'include',
    body: formData
  })
  return response.json()
}

export const syncSingleOrder = (orderId: string) =>
  request.post({ url: `/api/orders/${orderId}/refresh` })

export const manualShipOrder = (
  orderIds: string[],
  shipMode: ShipMode,
  content?: string
): Promise<ManualShipResponse> =>
  request.post({
    url: '/api/orders/manual-ship',
    data: {
      order_ids: orderIds,
      ship_mode: shipMode,
      custom_content: content
    }
  })

export const importOrders = async (data: Partial<Order>[] | FormData) => {
  const isFormData = data instanceof FormData
  const response = await fetch('/api/orders/import', {
    method: 'POST',
    credentials: 'include',
    headers: isFormData ? {} : { 'Content-Type': 'application/json' },
    body: isFormData ? data : JSON.stringify(data)
  })
  return response.json()
}

export const updateOrderStatus = (orderId: string, status: string) =>
  request.put({ url: `/api/orders/${orderId}/status`, data: { status } })
