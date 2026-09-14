import request from '@/utils/http'
import type { ShipMode, ManualShipResponse } from './types'

export const manualShipOrders = (
  orderIds: string[],
  shipMode: ShipMode = 'full_delivery',
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
