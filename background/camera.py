try:
    from hobot_vio import libsrcampy as srcampy
except ImportError:
    from hobot_vio_rdkx5 import libsrcampy as srcampy
try:
    from hobot_dnn import pyeasy_dnn as dnn
except ImportError:
    from hobot_dnn_rdkx5 import pyeasy_dnn as dnn
import threading
import time
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

h, w = 1024, 1024

if __name__ == '__main__':
    # signal.signal(signal.SIGINT, signal_handler)

    # Camera API, get camera object
    cam = srcampy.Camera()

    # get model info
    # h, w = h, w
    sensor_height, sensor_width = h, w
    input_shape = (h, w)
    # Open f37 camera
    # For the meaning of parameters, please refer to the relevant documents of camera
    # cam.open_cam(0, -1, -1, [w, w], [h, h],sensor_height,sensor_width)
    cam.open_cam(0, -1, 30, [w,1920], [h,1080],1080,1920)

    print("开始监听摄像帧")
    while not is_stop:
        raw = cam.get_img(2, h, w)
        if raw is None:
            continue
        
        # NV12 → BGR
        img_bytes = bytes(raw)
        nv12 = np.frombuffer(img_bytes, dtype=np.uint8)

        jpeg_bytes = nv12_to_jpeg_bytes(nv12, w, h, 85)
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
