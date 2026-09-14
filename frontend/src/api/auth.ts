import request from '@/utils/http'
import { HttpError } from '@/utils/http/error'
import { ApiStatus } from '@/utils/http/status'

/** Art Design Pro 登录入口 — 对接 Cookie Session */
export async function fetchLogin(params: Api.Auth.LoginParams) {
  const res = await request.post<{
    success: boolean
    message?: string
    user_id?: number
    username?: string
    is_admin?: boolean
  }>({
    url: '/login',
    data: { username: params.userName, password: params.password },
    showErrorMessage: false
  })
  if (!res?.success) {
    throw new HttpError(res?.message || '登录失败', ApiStatus.error)
  }
  return { token: 'cookie-session', refreshToken: '' }
}

export async function fetchGetUserInfo() {
  const res = await request.get<{
    authenticated: boolean
    initialized?: boolean
    user_id?: number
    username?: string
    is_admin?: boolean
  }>({ url: '/verify', showErrorMessage: false })

  if (!res?.authenticated) {
    throw new HttpError('未登录', ApiStatus.unauthorized)
  }

  const isAdmin = !!res.is_admin
  return {
    buttons: [] as string[],
    roles: isAdmin ? ['R_SUPER', 'R_ADMIN'] : ['R_USER'],
    userId: res.user_id || 0,
    userName: res.username || '',
    email: '',
    avatar: undefined
  } satisfies Api.Auth.UserInfo
}

export async function fetchLogout() {
  return request.post({ url: '/logout', data: {} })
}

export async function fetchVerifySession() {
  return request.get<{
    authenticated: boolean
    initialized?: boolean
    user_id?: number
    username?: string
    is_admin?: boolean
  }>({ url: '/verify', showErrorMessage: false })
}
