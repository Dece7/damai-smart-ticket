import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'light' | 'dark'

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>((localStorage.getItem('theme') as ThemeMode) || 'light')

  function toggle() {
    mode.value = mode.value === 'light' ? 'dark' : 'light'
  }

  function setTheme(m: ThemeMode) {
    mode.value = m
  }

  // 同步到 DOM 和 localStorage
  watch(mode, (v) => {
    document.documentElement.setAttribute('data-theme', v)
    localStorage.setItem('theme', v)
  }, { immediate: true })

  return { mode, toggle, setTheme }
})
