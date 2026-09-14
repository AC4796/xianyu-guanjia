import request from '@/utils/http'
import type { ApiResponse, User } from './types'

export const getUsers = async (): Promise<{ success: boolean; data?: User[] }> => {
  const result = await request.get<{
    users: Array<{
      id: number
      username: string
      email?: string
      is_admin: boolean
    }>
  }>({ url: '/admin/users' })
  const users: User[] = (result.users || []).map((u) => ({
    user_id: u.id,
    username: u.username,
    email: u.email,
    is_admin: u.is_admin
  }))
  return { success: true, data: users }
}

export const deleteUser = (userId: number) =>
  request.del<ApiResponse>({ url: `/admin/users/${userId}` })

export const getSystemLogs = async (params?: {
  page?: number
  limit?: number
  level?: string
}) => {
  const query: Record<string, string | number> = {}
  if (params?.page) query.page = params.page
  if (params?.limit) query.lines = params.limit
  if (params?.level) query.level = params.level.toUpperCase()
  const result = await request.get<{ logs?: string[]; total?: number }>({
    url: '/admin/logs',
    params: query
  })
  const logs = (result.logs || []).map((log, index) => ({
    id: String(index),
    level: log.includes('ERROR') ? 'error' : log.includes('WARNING') ? 'warning' : 'info',
    message: log,
    module: 'system',
    created_at: new Date().toISOString()
  }))
  return { success: true, data: logs, total: result.total }
}

export const clearSystemLogs = () => request.post<ApiResponse>({ url: '/admin/logs/clear' })

export const getRiskLogs = async (params?: {
  page?: number
  limit?: number
  cookie_id?: string
}) => {
  const result = await request.get<{ success: boolean; data?: any[]; total?: number }>({
    url: '/admin/risk-control-logs',
    params
  })
  const data = (result.data || []).map((item: any) => ({
    id: String(item.id),
    cookie_id: item.cookie_id,
    risk_type: item.event_type || item.risk_type,
    message: item.event_description || item.message,
    processing_result: item.processing_result,
    processing_status: item.processing_status,
    error_message: item.error_message,
    created_at: item.created_at,
    updated_at: item.updated_at
  }))
  return { success: true, data, total: result.total }
}

export const clearRiskLogs = () =>
  request.post<ApiResponse>({ url: '/admin/risk-control-logs/clear' })

export const getAdminStats = () => request.get({ url: '/admin/stats' })

export const getTableData = (tableName: string, page = 1, limit = 50) =>
  request.get({ url: `/admin/data/${tableName}`, params: { page, limit } })

export const clearTableData = (tableName: string) =>
  request.post({ url: `/admin/data/${tableName}/clear` })

export const deleteTableRecord = (tableName: string, recordId: string) =>
  request.del({ url: `/admin/data/${tableName}/${recordId}` })

export const exportLogs = async () => {
  const response = await fetch('/admin/logs/export', { credentials: 'include' })
  return response.blob()
}
