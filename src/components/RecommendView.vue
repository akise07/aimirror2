<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '../store/app'
import { fetchRecommend } from '../services/api'

const store = useAppStore()

// 状态
const isGenerating = ref(false)
const progress = ref(0)
const progressMsg = ref('')
const result = ref('')
const errorMsg = ref('')

// 流式读取取消控制器
let streamAbortController: AbortController | null = null

// 选择输入图片
const useCachedPhoto = ref(false)

async function startRecommend() {
  if (isGenerating.value) return
  if (!store.cachedPhoto) {
    errorMsg.value = '请先在首页拍照缓存身份图片'
    return
  }

  isGenerating.value = true
  progress.value = 0
  progressMsg.value = '准备中...'
  result.value = ''
  errorMsg.value = ''

  // 创建取消控制器
  streamAbortController = new AbortController()

  try {
    // 将 base64 转 Blob
    const res = await fetch(store.cachedPhoto)
    const blob = await res.blob()

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
      <p class="section-desc">AI 分析你的面部特征，为你推荐最适合的妆容方案</p>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="photo-check">
          <span>📸 使用拍照缓存图片</span>
          <span v-if="store.cachedPhoto" class="tag">✅ 已缓存</span>
          <span v-else class="tag" style="background: var(--bg-secondary); color: var(--text-muted);">❌ 未缓存</span>
        </div>
        <div v-if="store.cachedPhoto" class="preview-thumb">
          <img :src="store.cachedPhoto" alt="缓存照片" />
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <button
          class="btn btn-primary"
          :disabled="isGenerating || !store.cachedPhoto"
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

.input-area {
  margin-bottom: 20px;
}

.photo-check {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.preview-thumb {
  width: 120px;
  height: 120px;
  border-radius: 14px;
  overflow: hidden;
  border: 2px solid var(--accent);
  box-shadow: 0 4px 15px var(--shadow);
}

.preview-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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
