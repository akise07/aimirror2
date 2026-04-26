<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../store/app'
import { fetchRecommend, getIdentityImages } from '../services/api'

const store = useAppStore()
const router = useRouter()

// A类身份图片列表
const identityImages = getIdentityImages()

// 选中的图片
const selectedImage = ref<string | null>(null)   // 选中的图片路径
const useCachedPhoto = ref(false)                // 是否使用拍照缓存

// 状态
const isGenerating = ref(false)
const progress = ref(0)
const progressMsg = ref('')
const result = ref('')
const errorMsg = ref('')

// 流式读取取消控制器
let streamAbortController: AbortController | null = null

const canStart = computed(() => {
  const hasImage = useCachedPhoto.value ? !!store.cachedPhoto : !!selectedImage.value
  return hasImage && !isGenerating.value
})

function selectRefImage(img: string) {
  selectedImage.value = img
  useCachedPhoto.value = false
}

function selectCachedPhoto() {
  if (store.cachedPhoto) {
    useCachedPhoto.value = true
    selectedImage.value = null
  } else {
    // 没有缓存，跳转到拍照页面
    router.push('/camera')
  }
}

async function startRecommend() {
  if (!canStart.value) return

  isGenerating.value = true
  progress.value = 0
  progressMsg.value = '准备中...'
  result.value = ''
  errorMsg.value = ''

  // 创建取消控制器
  streamAbortController = new AbortController()

  try {
    // 获取图片 Blob
    let blob: Blob
    if (useCachedPhoto.value && store.cachedPhoto) {
      const res = await fetch(store.cachedPhoto)
      blob = await res.blob()
    } else if (selectedImage.value) {
      const res = await fetch(selectedImage.value)
      blob = await res.blob()
    } else {
      throw new Error('未选择图片')
    }

    // 调用流式推荐接口
    const stream = await fetchRecommend(blob)
    const reader = stream.getReader()
    const decoder = new TextDecoder()
    const signal = streamAbortController.signal

    let buffer = ''
    while (!signal.aborted) {
      const { done, value } = await reader.read()
      if (done) break
      if (signal.aborted) break

      buffer += decoder.decode(value, { stream: true })

      // 解析 MJPEG 流中的 JSON 数据
      const parts = buffer.split('--frame\r\n')
      for (const part of parts) {
        const jsonStart = part.indexOf('{')
        if (jsonStart === -1) continue

        const jsonStr = part.substring(jsonStart).trim()
        try {
          const data = JSON.parse(jsonStr)
          if (data.step !== undefined) {
            progress.value = data.step
            progressMsg.value = data.msg || ''
            if (data.step === 100 && data.result) {
              result.value = data.result
            }
          }
        } catch {
          // 忽略解析错误，继续读取
        }
      }
    }

    // 取消流读取
    reader.cancel().catch(() => {})
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    errorMsg.value = e.message || '推荐服务异常'
  } finally {
    isGenerating.value = false
    streamAbortController = null
  }
}

function resetRecommend() {
  // 取消正在进行的流式读取
  if (streamAbortController) {
    streamAbortController.abort()
    streamAbortController = null
  }
  isGenerating.value = false
  progress.value = 0
  progressMsg.value = ''
  result.value = ''
  errorMsg.value = ''
}
</script>

<template>
  <div class="recommend-view">
    <div class="section-card">
      <h2 class="section-title">🌟 妆容推荐</h2>
      <p class="section-desc">选择一张图片，AI 分析面部特征，为你推荐最适合的妆容方案</p>

      <!-- 图片选择区域 -->
      <div class="image-section">
        <span class="section-label">🖼️ 选择图片</span>
        <div class="image-grid">
          <!-- 拍照缓存框 - 固定在第一格 -->
          <div
            class="image-grid-item cached-photo-item"
            :class="{ selected: useCachedPhoto && !!store.cachedPhoto }"
            @click="selectCachedPhoto"
          >
            <template v-if="store.cachedPhoto">
              <img :src="store.cachedPhoto" alt="拍照缓存" />
              <div v-if="useCachedPhoto" class="check-mark">✓</div>
              <span class="cached-badge">📸 缓存</span>
            </template>
            <template v-else>
              <div class="cached-placeholder">
                <span class="placeholder-icon">📸</span>
                <span class="placeholder-text">尚未存储拍照缓存</span>
                <span class="placeholder-hint">前往拍照获取缓存</span>
              </div>
            </template>
          </div>

          <!-- 身份图片列表（A类） -->
          <div
            v-for="img in identityImages"
            :key="img"
            class="image-grid-item"
            :class="{ selected: selectedImage === img && !useCachedPhoto }"
            @click="selectRefImage(img)"
          >
            <img :src="img" :alt="img" />
            <div v-if="selectedImage === img && !useCachedPhoto" class="check-mark">✓</div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <button
          class="btn btn-primary"
          :disabled="!canStart"
          @click="startRecommend"
        >
          <span v-if="isGenerating">⏳ 分析中...</span>
          <span v-else>✨ 开始妆容推荐</span>
        </button>
        <button v-if="isGenerating || result" class="btn btn-secondary" @click="resetRecommend">
          🔄 重置
        </button>
      </div>

      <!-- 进度展示 -->
      <div v-if="isGenerating" class="progress-section">
        <div class="progress-info">
          <span class="progress-step">{{ progress }}%</span>
          <span class="progress-msg">{{ progressMsg }}</span>
        </div>
        <div class="progress-bar">
          <div class="progress-bar-fill" :style="{ width: progress + '%' }"></div>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="errorMsg" class="status-box error-box">
        <span>❌ {{ errorMsg }}</span>
      </div>

      <!-- 推荐结果 -->
      <div v-if="result" class="result-section">
        <h3 class="result-title">💖 妆容推荐结果</h3>
        <div class="result-content">
          <p v-for="(line, i) in result.split('\n')" :key="i">{{ line }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommend-view {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 24px;
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
  margin-bottom: 24px;
}

.image-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.section-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 拍照缓存框样式 */
.cached-photo-item {
  position: relative;
  cursor: pointer;
  background: var(--bg-secondary);
  border: 2px dashed var(--border);
}

.cached-photo-item:hover {
  border-style: solid;
}

.cached-badge {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  background: var(--accent);
  color: #fff;
  padding: 2px 10px;
  border-radius: 10px;
  white-space: nowrap;
  z-index: 2;
}

.cached-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  gap: 6px;
  padding: 12px;
}

.placeholder-icon {
  font-size: 20px;
  opacity: 0.5;
}

.placeholder-text {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  line-height: 1.4;
}

.placeholder-hint {
  font-size: 12px;
  color: var(--accent);
  text-align: center;
  opacity: 0.8;
}

.action-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.progress-section {
  margin-bottom: 20px;
}

.progress-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.progress-step {
  font-size: 16px;
  font-weight: 700;
  color: var(--accent);
}

.progress-msg {
  font-size: 13px;
  color: var(--text-secondary);
}

.status-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-radius: 14px;
  font-size: 14px;
}

.error-box {
  background: #fff0f0;
  color: var(--error);
}

.result-section {
  margin-top: 24px;
}

.result-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 16px;
}

.result-content {
  padding: 20px;
  background: var(--bg-secondary);
  border-radius: 16px;
  line-height: 1.8;
  font-size: 14px;
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.result-content p {
  margin-bottom: 4px;
}
</style>
