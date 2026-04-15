import { defineStore } from 'pinia'

export type ThemeMode = 'pink' | 'dark-pink' | 'warm' | 'cool'

interface AppState {
  theme: ThemeMode
  cachedPhoto: string | null       // 拍照缓存的身份图片 base64
  makeupResults: MakeupResult[]    // 妆容生成历史
  light1: number                   // 灯光1亮度 0-100
  light2: number                   // 灯光2亮度 0-100
}

export interface MakeupResult {
  taskId: string
  imageUrl: string
  timestamp: number
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    theme: 'pink',
    cachedPhoto: null,
    makeupResults: [],
    light1: 50,
    light2: 50,
  }),

  getters: {
    themeClass(state): string {
      const themeMap: Record<ThemeMode, string> = {
        'pink': '',
        'dark-pink': 'dark-pink',
        'warm': 'warm',
        'cool': 'cool',
      }
      return themeMap[state.theme]
    },
  },

  actions: {
    setTheme(theme: ThemeMode) {
      this.theme = theme
    },

    setCachedPhoto(base64: string) {
      this.cachedPhoto = base64
    },

    clearCachedPhoto() {
      this.cachedPhoto = null
    },

    addMakeupResult(result: MakeupResult) {
      this.makeupResults.unshift(result)
    },

    setLight1(value: number) {
      this.light1 = value
    },

    setLight2(value: number) {
      this.light2 = value
    },
  },
})
