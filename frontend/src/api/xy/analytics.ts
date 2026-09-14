import request from '@/utils/http'
import type { Order } from './types'

export const getOrderAnalytics = async (
  daysOrParams: number | { start_date: string; end_date: string } = 7
) => {
  let params: { start_date: string; end_date: string }
  if (typeof daysOrParams === 'number') {
    const endDate = new Date()
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - daysOrParams)
    params = {
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0]
    }
  } else {
    params = daysOrParams
  }
  return request.get({ url: '/analytics/orders', params })
}

export const getValidOrders = async (dateRange: {
  start_date: string
  end_date: string
}): Promise<Order[]> => {
  const res = await request.get<{ orders?: Order[] }>({
    url: '/analytics/orders/valid',
    params: dateRange
  })
  return res.orders || []
}
