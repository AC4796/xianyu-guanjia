import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getAccountDetails, type AccountCard } from '../api/accounts'

const KEY = 'xy_active_cookie_id'

export const useAccountStore = defineStore('account', () => {
  const activeCookieId = ref(localStorage.getItem(KEY) || '')
  const accounts = ref<AccountCard[]>([])
  const loading = ref(false)

  const activeAccount = computed(
    () => accounts.value.find((a) => a.id === activeCookieId.value) || accounts.value[0] || null
  )

  function setActive(id: string): void {
    activeCookieId.value = id
    if (id) localStorage.setItem(KEY, id)
    else localStorage.removeItem(KEY)
  }

  async function loadAccounts(): Promise<AccountCard[]> {
    loading.value = true
    try {
      accounts.value = await getAccountDetails()
      if (!activeCookieId.value && accounts.value[0]) {
        setActive(accounts.value[0].id)
      } else if (
        activeCookieId.value &&
        accounts.value.length &&
        !accounts.value.some((a) => a.id === activeCookieId.value)
      ) {
        setActive(accounts.value[0].id)
      }
      return accounts.value
    } finally {
      loading.value = false
    }
  }

  return {
    activeCookieId,
    accounts,
    loading,
    activeAccount,
    setActive,
    loadAccounts
  }
})
