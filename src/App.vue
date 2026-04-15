<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore, type ThemeMode } from './store/app'

const store = useAppStore()

const themeAttr = computed(() => {
  const map: Record<ThemeMode, string> = {
    'pink': '',
    'dark-pink': 'dark-pink',
    'warm': 'warm',
    'cool': 'cool',
  }
  return map[store.theme]
})

const currentPath = computed(() => {
  return window.location.hash.replace('#', '') || '/camera'
})
</script>

<template>
  <div class="app-container" :data-theme="themeAttr || undefined">
    <!-- 侧边导航 -->
    <nav class="side-nav">
      <div class="nav-logo">
        <span class="logo-icon">💄</span>
        <span class="logo-text">AIMakeup</span>
      </div>

      <div class="nav-links">
        <router-link to="/camera" class="nav-item" :class="{ active: currentPath === '/camera' }">
          <span class="nav-icon">📹</span>
          <span class="nav-label">实时预览</span>
        </router-link>
        <router-link to="/makeup" class="nav-item" :class="{ active: currentPath === '/makeup' }">
          <span class="nav-icon">💄</span>
          <span class="nav-label">妆容生成</span>
        </router-link>
        <router-link to="/video" class="nav-item" :class="{ active: currentPath === '/video' }">
          <span class="nav-icon">🎬</span>
          <span class="nav-label">视频生成</span>
        </router-link>
        <router-link to="/recommend" class="nav-item" :class="{ active: currentPath === '/recommend' }">
          <span class="nav-icon">🌟</span>
          <span class="nav-label">妆容推荐</span>
        </router-link>
      </div>

      <div class="nav-bottom">
        <router-link to="/settings" class="nav-item" :class="{ active: currentPath === '/settings' }">
          <span class="nav-icon">⚙️</span>
          <span class="nav-label">设置</span>
        </router-link>
      </div>
    </nav>

    <!-- 主内容区域 -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<style>
@import './styles/global.css';
</style>

<style scoped>
.app-container {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-primary);
}

/* 侧边导航 */
.side-nav {
  width: 200px;
  min-width: 200px;
  height: 100%;
  background: var(--bg-nav);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 12px;
  backdrop-filter: blur(10px);
  transition: background 0.3s ease;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}

.logo-icon {
  font-size: 28px;
}

.logo-text {
  font-size: 18px;
  font-weight: 800;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-links {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-bottom {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 14px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.25s ease;
  cursor: pointer;
}

.nav-item:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
  transform: translateX(4px);
}

.nav-item.active {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 4px 15px var(--shadow);
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.nav-label {
  white-space: nowrap;
}

/* 主内容 */
.main-content {
  flex: 1;
  height: 100%;
  overflow: hidden;
}
</style>
