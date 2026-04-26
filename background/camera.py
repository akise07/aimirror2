try:
    from hobot_vio import libsrcampy as srcampy
except ImportError:
    from hobot_vio_rdkx5 import libsrcampy as srcampy
try:
    from hobot_dnn import pyeasy_dnn as dnn
except ImportError:
    from hobot_dnn_rdkx5 import pyeasy_dnn as dnn
import threading
import time,sys
import multiprocessing
import signal, requests
import numpy as np
from PIL import Image
import cv2, io

is_stop=False
SERVER_URL = "http://localhost:3401"

def nv12_to_jpeg_bytes(nv12_data, width, height, quality=85):
    """
    将 NV12 数据转换为 JPEG 二进制数据
    
    参数:
        nv12_data: bytes 或 numpy array, NV12 格式的原始数据
        width: 图像宽度
        height: 图像高度
        quality: JPEG 质量 (1-95)
    
    返回:
        JPEG 二进制数据 (bytes)
    """
    # 确保数据是 numpy array
    if isinstance(nv12_data, bytes):
        nv12_data = np.frombuffer(nv12_data, dtype=np.uint8)
    
    # NV12 格式: Y 平面 (width * height) + UV 交错平面 (width * height / 2)
    # Y 平面大小
    y_size = width * height
    # UV 平面大小 (U 和 V 交错存储)
    uv_size = width * height // 2
    
    # 分离 Y 和 UV 平面
    y_plane = nv12_data[:y_size].reshape((height, width))
    uv_plane = nv12_data[y_size:y_size + uv_size].reshape((height // 2, width))
    
    # 分离 U 和 V (UV 交错存储: U0, V0, U1, V1, ...)
    u_plane = uv_plane[:, 0::2]
    v_plane = uv_plane[:, 1::2]
    
    # 上采样 U 和 V 到完整尺寸
    u_full = np.repeat(np.repeat(u_plane, 2, axis=0), 2, axis=1)
    v_full = np.repeat(np.repeat(v_plane, 2, axis=0), 2, axis=1)
    
    # YUV 转 RGB
    # 公式: R = Y + 1.402(V - 128)
    #       G = Y - 0.344134(U - 128) - 0.714136(V - 128)
    #       B = Y + 1.772(U - 128)
    
    y = y_plane.astype(np.float32)
    u = u_full.astype(np.float32) - 128
    v = v_full.astype(np.float32) - 128
    
    r = np.clip(y + 1.402 * v, 0, 255).astype(np.uint8)
    g = np.clip(y - 0.344134 * u - 0.714136 * v, 0, 255).astype(np.uint8)
    b = np.clip(y + 1.772 * u, 0, 255).astype(np.uint8)
    
    # 合并 RGB 通道
    rgb_image = np.stack([r, g, b], axis=2)
    
    # 转换为 PIL Image 并保存为 JPEG
    pil_image = Image.fromarray(rgb_image, 'RGB')

    pil_image = pil_image.transpose(Image.FLIP_TOP_BOTTOM)
    
    # 保存到内存缓冲区
    buffer = io.BytesIO()
    pil_image.save(buffer, format='JPEG', quality=quality, optimize=True)
    jpeg_bytes = buffer.getvalue()
    
    return jpeg_bytes

ASPECT_W, ASPECT_H = 1920, 1080

def nv12_stretch_crop(nv12, src_h, src_w, crop_size):
    """
    NV12 numpy array (src_h×src_w, 变形) → 拉伸恢复纵横比 → 中心裁剪 → NV12 bytes
    """
    # 分离 Y 和 UV 平面
    y_size = src_h * src_w
    y_plane = nv12[:y_size].reshape(src_h, src_w)
    uv_plane = nv12[y_size:].reshape(src_h // 2, src_w)

    # 拉伸后目标宽度
    new_w = int(src_h * ASPECT_W / ASPECT_H)  # 512 → 910

    # Y 平面: (512, 512) → (512, 910)
    y_stretched = cv2.resize(y_plane, (new_w, src_h), interpolation=cv2.INTER_LINEAR)

    # UV 平面: (256, 512) → (256, 910)，reshape成双通道防止U/V交叉
    uv_2ch = uv_plane.reshape(src_h // 2, src_w // 2, 2)
    uv_2ch = cv2.resize(uv_2ch, (new_w // 2, src_h // 2), interpolation=cv2.INTER_LINEAR)
    uv_stretched = uv_2ch.reshape(src_h // 2, new_w)

    # 中心裁剪
    x1 = (new_w - crop_size) // 2  # 199
    y1 = (src_h - crop_size) // 2  # 0

    y_crop = y_stretched[y1:y1 + crop_size, x1:x1 + crop_size]
    uv_crop = uv_stretched[y1 // 2:(y1 + crop_size) // 2, x1:x1 + crop_size]

    # 合并回 NV12
    out = np.empty(crop_size * crop_size * 3 // 2, dtype=np.uint8)
    out[:crop_size * crop_size] = y_crop.ravel()
    out[crop_size * crop_size:] = uv_crop.ravel()
    return out.tobytes()

def nv12_stretch_crop_to_jpeg(nv12, src_h, src_w, crop_size, quality=85):
    """
    NV12 → BGR → 拉伸恢复纵横比 → 中心裁剪 → JPEG
    全程 OpenCV 处理，不手动拆 Y/UV 平面
    """
    # OpenCV 自动处理 stride，不依赖紧密排列
    bgr = cv2.cvtColor(nv12.reshape(-1, src_w), cv2.COLOR_YUV2BGR_NV12)

    bgr = cv2.flip(bgr, 0)

    bgr = cv2.bilateralFilter(bgr, 9, 75, 75)


    # 拉伸宽度恢复纵横比: 512x512 → 910x512
    new_w = int(src_h * ASPECT_W / ASPECT_H)
    stretched = cv2.resize(bgr, (new_w, src_h), interpolation=cv2.INTER_LINEAR)

    # 中心裁剪 512x512
    x1 = (new_w - crop_size) // 2
    cropped = stretched[:, x1:x1 + crop_size]

    # BGR → JPEG
    _, buf = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()

# Camera API, get camera object
cam = srcampy.Camera()

def signal_handler(signal, frame):
    global is_stop, cam
    print("Stopping!\n")
    is_stop=True
    cam.close_cam()
    sys.exit(0)


h, w = 512, 512

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)

    

    # get model info
    # h, w = h, w
    sensor_height, sensor_width = h, w
    input_shape = (h, w)
    # Open f37 camera
    # For the meaning of parameters, please refer to the relevant documents of camera
    # cam.open_cam(0, -1, -1, [w, w], [h, h],sensor_height,sensor_width)
    cam.open_cam(0, -1, 30, [w,w], [h,h],1080,1920)

    print("开始监听摄像帧")
    while not is_stop:
        raw = cam.get_img(2, h, w)
        if raw is None:
            continue
        
        # NV12 → BGR
        img_bytes = bytes(raw)
        nv12 = np.frombuffer(img_bytes, dtype=np.uint8)

        # nv12 = nv12_stretch_crop(nv12, h, w, w)

        # jpeg_bytes = nv12_to_jpeg_bytes(nv12, w, h, 85)
        jpeg_bytes = nv12_stretch_crop_to_jpeg(nv12, h, w, w, 85)
        # bgr = cv2.cvtColor(nv12.reshape(512*2,512), cv2.COLOR_YUV2BGR_NV12)

        # # BGR → JPEG
        # _, buf = cv2.imencode(".jpg", bgr)
        # jpeg_bytes = buf.tobytes()

        # 保存到文件
        # with open("output.jpg", "wb") as f:
        #     f.write(jpeg_bytes)

        # time.sleep(5)

        # 直接发原始JPEG字节
        try:
            requests.post(f"{SERVER_URL}/frame_upload", data=jpeg_bytes, timeout=2.0)
        except Exception as e:
            print(f"发送失败: {e}")
        
        time.sleep(0.033)

    cam.close_cam()
