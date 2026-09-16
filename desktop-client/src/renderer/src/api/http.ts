/** API 根地址：开发走 Vite 代理；打包后走 Electron 同源网关（相对路径，Cookie 可带上） */
export function apiBase(): string {
  return ''
}

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(message: string, status: number, body?: unknown) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function resolveUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url
  const base = apiBase()
  if (!base) return url
  return `${base}${url.startsWith('/') ? url : `/${url}`}`
}

export async function request<T = unknown>(
  url: string,
  options: RequestInit & { json?: unknown; timeoutMs?: number } = {}
): Promise<T> {
  const { json, headers, timeoutMs, ...rest } = options
  const ctrl = timeoutMs && timeoutMs > 0 ? new AbortController() : null
  const timer = ctrl ? window.setTimeout(() => ctrl.abort(), timeoutMs) : 0
  let res: Response
  try {
    res = await fetch(resolveUrl(url), {
      credentials: 'include',
      ...rest,
      signal: ctrl?.signal || rest.signal,
      headers: {
        Accept: 'application/json',
        ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(headers as Record<string, string>)
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body
    })
  } catch (e: any) {
    if (ctrl) window.clearTimeout(timer)
    if (e?.name === 'AbortError') {
      throw new ApiError('采集超时，请确认账号在线后重试', 408)
    }
    throw e
  }
  if (ctrl) window.clearTimeout(timer)
  const body = await parseBody(res)
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`
    if (body && typeof body === 'object') {
      const o = body as Record<string, unknown>
      const detail = o.detail
      if (typeof o.message === 'string' && o.message) msg = o.message
      else if (typeof detail === 'string' && detail) msg = detail
      else if (detail && typeof detail === 'object') {
        const d = detail as Record<string, unknown>
        if (typeof d.message === 'string' && d.message) msg = d.message
      }
    }
    if (res.status === 401) {
      msg = '登录已过期，请重新登录'
      try {
        const path = window.location.hash || window.location.pathname || ''
        if (!path.includes('/login')) {
          window.location.hash = '#/login'
        }
      } catch {
        /* ignore */
      }
    }
    if (/Timeout context/i.test(msg) || /timeout/i.test(msg)) {
      msg = '请求超时：请确认账号在线后重试'
    }
    throw new ApiError(msg, res.status, body)
  }
  return body as T
}

export async function requestForm<T = unknown>(url: string, form: FormData): Promise<T> {
  const res = await fetch(resolveUrl(url), {
    method: 'POST',
    credentials: 'include',
    body: form
  })
  const body = await parseBody(res)
  if (!res.ok) {
    throw new ApiError(`请求失败 (${res.status})`, res.status, body)
  }
  return body as T
}
