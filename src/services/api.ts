/**
 * API 服务层 - 封装所有后端 API 调用
 * 本地后端: http://localhost:3401
 * 云端后端: http://localhost:3402
 */

// const LOCAL_BASE = 'http://localhost:3401'
// const CLOUD_BASE = 'http://localhost:3402'
const LOCAL_BASE = 'http://192.168.137.151:3401/'
const CLOUD_BASE = 'http://localhost:3402'

/** 妆容生成 - 创建任务 */
export async function createMakeupTask(imageId: File, imageRef: File) {
  const formData = new FormData()
  formData.append('image_id', imageId)
  formData.append('image_ref', imageRef)
  const res = await fetch(`${LOCAL_BASE}/makeup_image`, {
    method: 'POST',
    body: formData,
  })
  return res.json()
}

/** 妆容生成 - 获取任务状态 */
export async function getMakeupState(taskId: string) {
  const res = await fetch(`${LOCAL_BASE}/makeup_state`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskId }),
  })
  return res.json()
}

/** 视频生成 - 创建任务（FormData: image_id 文件上传 + text） */
export async function createVideoTask(imageId: File, text: string) {
  const formData = new FormData()
  formData.append('image_id', imageId)
  formData.append('text', text)
  const res = await fetch(`${LOCAL_BASE}/video_gen`, {
    method: 'POST',
    body: formData,
  })
  return res.json()
}

/** 视频生成 - 获取任务状态 */
export async function getVideoState(taskId: string) {
  const res = await fetch(`${LOCAL_BASE}/video_state`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskId }),
  })
  return res.json()
}

/** 调光 */
export async function setLight(light1Value: number, light2Value: number) {
  const res = await fetch(`${LOCAL_BASE}/set_light`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ light1_value: light1Value, light2_value: light2Value }),
  })
  return res.json()
}

/** 视频流地址 */
export function getVideoFeedUrl() {
  return `${LOCAL_BASE}/video_feed`
}

/** 妆容推荐 - 流式接口 */
export async function fetchRecommend(imageData: Blob): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`${CLOUD_BASE}/recommend`, {
    method: 'POST',
    body: imageData,
  })
  if (!res.body) throw new Error('No response body')
  return res.body
}

/** 获取身份图片列表（A类，a开头）- 用于妆容生成身份图和妆容推荐 */
export function getIdentityImages(): string[] {
  const images = [
    'a1.jpg', 'a2.jpg', 'a3.png', 'a4.jpg', 'a5.jpg',
    'a6.jpg', 'a7.jpg', 'a8.jpg', 'a9.jpg', 'a10.jpg'
  ]
  return images.map(name => `/ref/${name}`)
}

/** 获取参考妆容图片列表（B类，b开头）- 用于妆容生成参考妆效 */
export function getMakeupRefImages(): string[] {
  const images = [
    'b1.jpg', 'b2.jpg', 'b3.jpg', 'b4.jpg', 'b5.jpg',
    'b6.jpg', 'b10.jpg'
  ]
  return images.map(name => `/ref/${name}`)
}

/** 获取妆容生成结果图片地址 */
export function getMakeupResultUrl(taskId: string) {
  return `${LOCAL_BASE}/cache/makeup_img/${taskId}.jpg`
}

/** 获取视频生成结果地址（由 video_state 返回的 fileUrl） */
export function getVideoResultUrl(fileUrl: string) {
  return fileUrl
}
