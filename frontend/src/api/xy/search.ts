import request from '@/utils/http'

export const searchItems = (params: {
  keyword: string
  page?: number
  page_size?: number
  [key: string]: unknown
}) =>
  request.post<{
    success: boolean
    data?: any[]
    items?: any[]
    total?: number
    error?: string
  }>({
    url: '/items/search',
    data: {
      keyword: params.keyword,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20
    }
  })
