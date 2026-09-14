import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { darkTheme, type GlobalTheme } from 'naive-ui'

const KEY = 'xy_theme_mode'

export type ThemeMode = 'light' | 'dark'

function applyDomTheme(mode: ThemeMode): void {
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark')
  root.dataset.theme = mode
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>((localStorage.getItem(KEY) as ThemeMode) || 'light')
  applyDomTheme(mode.value)

  const naiveTheme = computed<GlobalTheme | null>(() =>
    mode.value === 'dark' ? darkTheme : null
  )

  function setMode(next: ThemeMode): void {
    mode.value = next
    localStorage.setItem(KEY, next)
    applyDomTheme(next)
  }

  function toggle(): void {
    setMode(mode.value === 'dark' ? 'light' : 'dark')
  }

  watch(mode, (m) => applyDomTheme(m), { immediate: true })

  return { mode, naiveTheme, setMode, toggle }
})
