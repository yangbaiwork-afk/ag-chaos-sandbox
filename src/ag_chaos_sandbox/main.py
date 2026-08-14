import asyncio
import json
import math
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()

# 挂载静态文件(基于包自身的绝对路径,避免依赖 CWD)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def get_index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        start_time = time.time()
        while True:
            # --- 这里模拟未来MuJoCo 和 Ontology 算出来的物理状态 ---
            t = time.time() - start_time

            # 用正弦波模拟机械臂的虚拟运动轨迹（假数据）
            arm_x = math.sin(t) * 2.0
            arm_y = math.cos(t) * 2.0

            # 模拟随机环境干扰导致的HP 变化（测试UI响应）
            current_hp = 100 if int(t) % 10 < 5 else 75
            status_msg = "Safe" if current_hp == 100 else "Warning: Damage Detected"

            # 组装极简的 JSON Payload
            payload = {
                "arm_position": [arm_x, arm_y, 0.0],
                "tomato_hp": current_hp,
                "system_status": status_msg
            }

            # 推送给前端
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.05)  # 20Hz 刷新率

    except WebSocketDisconnect:
        print("Client disconnected")

        

