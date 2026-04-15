<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../store/app'
import { getVideoFeedUrl } from '../services/api'

const store = useAppStore()
const videoError = ref(false)
const streamUrl = ref('')

onMounted(() => {
  streamUrl.value = getVideoFeedUrl()
})

function capturePhoto() {
  const video = document.querySelector('.camera-video') as HTMLImageElement
  if (!video) return

  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 1024
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.drawImage(video, 0, 0, 1024, 1024)
  const base64 = canvas.toDataURL('image/jpeg', 0.9)
  store.setCachedPhoto(base64)
}

function handleVideoError() {
  videoError.value = true
}
</script>

<template>
  <div class="camera-view">
    <div class="camera-container">
      <div class="video-wrapper">
        <img
          v-if="!videoError"
          :src="streamUrl"
          class="camera-video"
          alt="📹 摄像头画面"
          @error="handleVideoError"
        />
        <div v-else class="video-placeholder">
          <span class="placeholder-icon">📹</span>
          <p>摄像头未连接</p>
          <p class="hint">请检查硬件连接状态</p>
        </div>
        <div class="video-badge">
          <span class="badge-dot"></span>
          <span>LIVE</span>
        </div>
      </div>
      <div class="camera-actions">
        <button class="capture-btn" @click="capturePhoto" title="📸 拍照">
          <span class="capture-icon">📸</span>
          <span>拍照</span>
        </button>
        <div v-if="store.cachedPhoto" class="cached-preview">
          <img :src="store.cachedPhoto" alt="已拍照片" class="cached-img" />
          <span class="cached-tag">✅ 已缓存</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.camera-view {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-container {
  display: flex;
  gap: 24px;
  align-items: center;
}

.video-wrapper {
  position: relative;
  width: 560px;
  height: 560px;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 8px 40px var(--shadow-strong);
  border: 2px solid var(--border);
  background: #000;
}

.camera-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.video-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.hint {
  font-size: 13px;
  margin-top: 8px;
  color: var(--text-muted);
}

.video-badge {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 20px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
}

.badge-dot {
  width: 8px;
  height: 8px;
  background: #ff4444;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

.camera-actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
}

.capture-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 28px;
  border-radius: 20px;
  border: 2px solid var(--border);
  background: var(--bg-card);
  cursor: pointer;
  transition: all 0.3s ease;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 4px 15px var(--shadow);
}

.capture-btn:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  transform: scale(1.05);
  box-shadow: 0 6px 20px var(--shadow-strong);
}

.capture-icon {
  font-size: 32px;
}

.cached-preview {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid var(--accent);
  box-shadow: 0 4px 15px var(--shadow);
}

.cached-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cached-tag {
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 9px;
  background: var(--accent);
  color: #fff;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
}
</style>
