import request from '@/utils/http'

export interface AlertNotice {
  title: string
  time?: string
  type?: string
  cookie_id?: string
}

export interface AlertMessage {
  title: string
  time?: string
  avatar?: string
  cookie_id?: string
}

export interface AlertPending {
  title: string
  time?: string
  cookie_id?: string
  action?: string
}

export interface AlertsPayload {
  notices: AlertNotice[]
  messages: AlertMessage[]
  pending: AlertPending[]
  abnormal_count?: number
}

export const getAlerts = async (): Promise<AlertsPayload> => {
  const res = await request.get<{ success: boolean; data: AlertsPayload }>({
    url: '/api/alerts'
  })
  return (
    res?.data || {
      notices: [],
      messages: [],
      pending: [],
      abnormal_count: 0
    }
  )
}
