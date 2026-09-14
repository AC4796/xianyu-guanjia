import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  login as apiLogin,
  logout as apiLogout,
  verifySession,
  type VerifyResponse
} from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const loading = ref(true)
  const authenticated = ref(false)
  const initialized = ref(true)
  const username = ref('')
  const userId = ref<number | null>(null)
  const isAdmin = ref(false)

  function apply(data: VerifyResponse): void {
    initialized.value = data.initialized !== false
    authenticated.value = !!data.authenticated
    if (data.authenticated) {
      username.value = data.username || ''
      userId.value = data.user_id ?? null
      isAdmin.value = !!data.is_admin
    } else {
      username.value = ''
      userId.value = null
      isAdmin.value = false
    }
  }

  async function refresh(): Promise<void> {
    try {
      const data = await verifySession()
      apply(data)
    } catch {
      authenticated.value = false
    } finally {
      loading.value = false
    }
  }

  async function login(user: string, password: string): Promise<{ ok: boolean; message: string }> {
    const res = await apiLogin({ username: user, password })
    if (!res.success) return { ok: false, message: res.message || '登录失败' }
    await refresh()
    return { ok: true, message: res.message || '登录成功' }
  }

  async function logout(): Promise<void> {
    try {
      await apiLogout()
    } finally {
      authenticated.value = false
      username.value = ''
      userId.value = null
    }
  }

  return {
    loading,
    authenticated,
    initialized,
    username,
    userId,
    isAdmin,
    refresh,
    login,
    logout
  }
})
