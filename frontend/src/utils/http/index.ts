/**
 * HTTP 请求封装 — 适配闲鱼管家 FastAPI（Cookie Session + 原始 JSON 响应）
 */
import axios, { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { useUserStore } from '@/store/modules/user'
import { ApiStatus } from './status'
import { HttpError, handleError, showError, showSuccess } from './error'
import { $t } from '@/locales'

const REQUEST_TIMEOUT = 60000
const LOGOUT_DELAY = 500
const UNAUTHORIZED_DEBOUNCE_TIME = 3000

let isUnauthorizedErrorShown = false
let unauthorizedTimer: ReturnType<typeof setTimeout> | null = null

interface ExtendedAxiosRequestConfig extends AxiosRequestConfig {
  showErrorMessage?: boolean
  showSuccessMessage?: boolean
  /** 若为 true，按 Art Design Pro 标准 {code,msg,data} 解包；默认 false，返回完整响应体 */
  standardResponse?: boolean
}

const { VITE_API_URL, VITE_WITH_CREDENTIALS } = import.meta.env

const axiosInstance = axios.create({
  timeout: REQUEST_TIMEOUT,
  baseURL: VITE_API_URL,
  withCredentials: VITE_WITH_CREDENTIALS === 'true',
  validateStatus: (status) => status >= 200 && status < 300
})

axiosInstance.interceptors.request.use(
  (request: InternalAxiosRequestConfig) => {
    const { accessToken } = useUserStore()
    // 后端已改为 Cookie Session；保留占位 token 仅用于前端登录态判断
    if (accessToken && accessToken !== 'cookie-session') {
      request.headers.set('Authorization', `Bearer ${accessToken}`)
    }

    if (request.data && !(request.data instanceof FormData) && !request.headers['Content-Type']) {
      request.headers.set('Content-Type', 'application/json')
    }

    return request
  },
  (error) => {
    showError(createHttpError($t('httpMsg.requestConfigError'), ApiStatus.error))
    return Promise.reject(error)
  }
)

axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    if (error.response?.status === ApiStatus.unauthorized) {
      handleUnauthorizedError()
    }
    return Promise.reject(handleError(error))
  }
)

function createHttpError(message: string, code: number) {
  return new HttpError(message, code)
}

function handleUnauthorizedError(message?: string): never {
  const error = createHttpError(message || $t('httpMsg.unauthorized'), ApiStatus.unauthorized)

  if (!isUnauthorizedErrorShown) {
    isUnauthorizedErrorShown = true
    logOut()
    unauthorizedTimer = setTimeout(resetUnauthorizedError, UNAUTHORIZED_DEBOUNCE_TIME)
    showError(error, true)
    throw error
  }

  throw error
}

function resetUnauthorizedError() {
  isUnauthorizedErrorShown = false
  if (unauthorizedTimer) clearTimeout(unauthorizedTimer)
  unauthorizedTimer = null
}

function logOut() {
  setTimeout(() => {
    useUserStore().logOut()
  }, LOGOUT_DELAY)
}

/** 请求函数：默认返回后端完整 JSON；standardResponse 时解包 data */
async function request<T = any>(config: ExtendedAxiosRequestConfig): Promise<T> {
  if (
    ['POST', 'PUT'].includes(config.method?.toUpperCase() || '') &&
    config.params &&
    !config.data
  ) {
    config.data = config.params
    config.params = undefined
  }

  try {
    const res = await axiosInstance.request(config)
    const body = res.data

    if (config.standardResponse && body && typeof body === 'object' && 'code' in body) {
      if (body.code === ApiStatus.success) {
        if (config.showSuccessMessage && body.msg) showSuccess(body.msg)
        return body.data as T
      }
      if (body.code === ApiStatus.unauthorized) handleUnauthorizedError(body.msg)
      throw createHttpError(body.msg || $t('httpMsg.requestFailed'), body.code)
    }

    if (config.showSuccessMessage && body?.message) {
      showSuccess(body.message)
    }

    return body as T
  } catch (error) {
    if (error instanceof HttpError && error.code !== ApiStatus.unauthorized) {
      const showMsg = config.showErrorMessage !== false
      showError(error, showMsg)
    }
    return Promise.reject(error)
  }
}

const api = {
  get<T>(config: ExtendedAxiosRequestConfig) {
    return request<T>({ ...config, method: 'GET' })
  },
  post<T>(config: ExtendedAxiosRequestConfig) {
    return request<T>({ ...config, method: 'POST' })
  },
  put<T>(config: ExtendedAxiosRequestConfig) {
    return request<T>({ ...config, method: 'PUT' })
  },
  del<T>(config: ExtendedAxiosRequestConfig) {
    return request<T>({ ...config, method: 'DELETE' })
  },
  request<T>(config: ExtendedAxiosRequestConfig) {
    return request<T>(config)
  }
}

export default api
