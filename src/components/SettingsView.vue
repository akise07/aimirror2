<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore, type ThemeMode } from '../store/app'
import { setLight } from '../services/api'

const store = useAppStore()

// 主题选项
const themes: { key: ThemeMode; label: string; emoji: string; desc: string }[] = [
  { key: 'pink', label: '白粉主题', emoji: '🌸', desc: '清新粉嫩' },
  { key: 'dark-pink', label: '黑粉主题', emoji: '🌹', desc: '暗夜玫瑰' },
  { key: 'warm', label: '暖色主题', emoji: '🌅', desc: '温暖如初' },
  { key: 'cool', label: '冷色主题', emoji: '💎', desc: '清冷优雅' },
]

const currentTheme = computed(() => store.theme)

// 调光
const light1 = ref(store.light1)
const light2 = ref(store.light2)
const lightSaving = ref(false)

async function onLightChange() {
  lightSaving.value = true
  try {
    await setLight(light1.value, light2.value)
    store.setLight1(light1.value)
    store.setLight2(light2.value)
  } catch {
    // 静默处理
  }
  lightSaving.value = false
}

function selectTheme(key: ThemeMode) {
  store.setTheme(key)
}
</script>

<template>
  <div class="settings-view">
    <div class="section-card">
      <!-- 主题切换 -->
      <h2 class="section-title">🎨 主题切换</h2>
      <p class="section-desc">选择你喜欢的界面风格</p>

      <div class="theme-grid">
        <div
          v-for="theme in themes"
          :key="theme.key"
          class="theme-card"
          :class="{ active: currentTheme === theme.key }"
          @click="selectTheme(theme.key)"
        >
          <span class="theme-emoji">{{ theme.emoji }}</span>
          <span class="theme-name">{{ theme.label }}</span>
          <span class="theme-desc">{{ theme.desc }}</span>
          <div v-if="currentTheme === theme.key" class="theme-check">✓</div>
        </div>
      </div>
    </div>

    <div class="section-card">
      <!-- 调光 -->
      <h2 class="section-title">💡 灯光调节</h2>
      <p class="section-desc">调节硬件补光灯亮度</p>

      <div class="light-controls">
        <div class="light-item">
          <div class="light-header">
            <span class="light-label">🔆 灯光 1</span>
            <span class="light-value">{{ light1 }}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            v-model.number="light1"
            @change="onLightChange"
            class="light-slider"
          />
        </div>
        <div class="light-item">
          <div class="light-header">
            <span class="light-label">🔆 灯光 2</span>
            <span class="light-value">{{ light2 }}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            v-model.number="light2"
            @change="onLightChange"
            class="light-slider"
          />
        </div>
      </div>
      <div v-if="lightSaving" class="saving-hint">
        <div class="loading-spinner"></div>
        <span>保存中...</span>
      </div>
    </div>

    <div class="section-card">
      <!-- 关于 -->
      <h2 class="section-title">💌 关于</h2>
      <div class="about-content">
        <div class="about-logo">💄</div>
        <h3 class="about-name">AIMakeup 美妆镜应用</h3>
        <p class="about-desc">
          AIMakeup 美妆镜应用，旨在通过人工智能技术为用户提供智能化的美妆体验。
          集成 AI 妆容生成、视频创作、智能推荐等功能，帮助每一位用户发现最适合自己的美丽方案。
          无论是日常淡妆还是精致妆容，AI 美妆镜都是你贴心的美妆顾问 💖
        </p>
        <div class="about-info">
          <span class="about-version">v1.0.0</span>
          <span class="about-divider">|</span>
          <span>Powered by AI ✨</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-card {
  background: var(--bg-card);
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 4px 20px var(--shadow);
  border: 1px solid var(--border);
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

/* 主题网格 */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.theme-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 16px;
  border-radius: 16px;
  border: 2px solid var(--border);
  cursor: pointer;
  transition: all 0.3s ease;
  background: var(--input-bg);
}

.theme-card:hover {
  border-color: var(--accent);
  transform: translateY(-3px);
  box-shadow: 0 6px 20px var(--shadow);
}

.theme-card.active {
  border-color: var(--accent);
  background: var(--accent-light);
  box-shadow: 0 6px 20px var(--shadow-strong);
}

.theme-emoji {
  font-size: 36px;
}

.theme-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.theme-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.theme-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background: var(--accent);
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
}

/* 灯光控制 */
.light-controls {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.light-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.light-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.light-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.light-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--accent);
  min-width: 40px;
  text-align: right;
}

.light-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  outline: none;
  transition: all 0.2s ease;
}

.light-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--accent);
  cursor: pointer;
  box-shadow: 0 2px 8px var(--shadow-strong);
  transition: all 0.2s ease;
}

.light-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.saving-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-muted);
}

/* 关于 */
.about-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}

.about-logo {
  font-size: 56px;
}

.about-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.about-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.8;
  max-width: 500px;
}

.about-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-muted);
}

.about-version {
  color: var(--accent);
  font-weight: 600;
}

.about-divider {
  color: var(--border);
}
</style>
