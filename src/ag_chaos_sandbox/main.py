import asyncio
import json
import threading
import math
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import mujoco

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()

# 挂载静态文件(基于包自身的绝对路径,避免依赖 CWD)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# =========== 1. Cross thread sharing status(The State Bridge) ==============
# This is the bridge between "Physics world" and "Network World"
twin_state = {
    "arm_skeleton": [],  # 存储所有关节的坐标
    "target_position": [0.0, 0.0, 0.0],
    "tomato_hp": 100,
    "system_status": "System Normal"
}

# =========== 2. Physics simulate thread(The Physics Daemon) ================
def run_physics_engine():
    global twin_state
    print("[后台] 正在启动 MuJoCo 物理线程...")

    # 使用安全的字符串加载方式
    with open("src/ag_chaos_sandbox/static/sandbox_env.xml", "r", encoding="utf-8") as f:
        xml_string = f.read()

    model = mujoco.MjModel.from_xml_string(xml_string)
    data = mujoco.MjData(model)
    sensor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "flower_collision")

    start_time = time.time()

    # 找到目标作物（Body）的ID
    flower_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "tomato_flower")

    # Physics main loop (永不阻塞网络)
    while True:
        step_start = time.time()
        t = time.time() - start_time

        # 模拟外部控制指令：让机械臂根关节来回扫动
        data.qpos[0] = math.sin(t) * 1.5

        # 执行物理步进
        mujoco.mj_step(model, data)

        # 1. 实时提取目标作物的真实3D 绝对坐标
        flower_pos = data.xpos[flower_body_id]
        twin_state["target_position"] = [float(flower_pos[0]), float(flower_pos[1]), float(flower_pos[2])]

        # 2. 提取末端执行器的真实3D坐标并更新给全局状态
        # （假设 end_effector 胶囊体的 geom ID 为 1， 实际中可通过名字获取）
        # 【新增/修改】提取骨架坐标：根部 -> 关节1 -> 关节2 -> 末端
        j1_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint1")
        j2_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint2")
        ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")

        j1_pos = data.xanchor[j1_id]
        j2_pos = data.xanchor[j2_id]
        ee_pos = data.geom_xpos[ee_id]

        twin_state["arm_skeleton"] = [
            [0.0, 0.0, 0.1],  # 基座位置
            [float(j1_pos[0]), float(j1_pos[1]), float(j1_pos[2])],
            [float(j2_pos[0]), float(j2_pos[1]), float(j2_pos[2])],
            [float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])]
        ]

        # 3. 基于空间距离的“幽灵触发器”
        # 碰撞逻辑依然使用计算最后一个节点(ee_pos)和 flower_pos 的距离
        dx, dy, dz = ee_pos[0] - flower_pos[0], ee_pos[1] - flower_pos[1], ee_pos[2] - flower_pos[2]
        if math.sqrt(dx ** 2 + dy ** 2 + dz ** 2) < 0.12 and twin_state["tomato_hp"] > 0:
            twin_state["tomato_hp"] -= 0.2
        if twin_state["tomato_hp"] < 95:
            twin_state["system_status"] = "CRITICAL: Damage Detected!"
        elif twin_state["tomato_hp"] >= 95:
            twin_state["system_status"] = "System Normal"

        # 锁频，保持与物理世界事件一致
        time_util_next = model.opt.timestep - (time.time() - step_start)
        if time_util_next > 0:
            time.sleep(time_util_next)

# 在 FastAPI 启动前，开启物理线程
physics_thread = threading.Thread(target=run_physics_engine, daemon=True)
physics_thread.start()

# ================ 3. 网络分发端（FastAPI 路由） =============
@app.get("/")
async def get_index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[网络] 前端数字孪生面板已连接")
    try:
        start_time = time.time()
        while True:
            # 极速打包共享状态并推流（这里只读不写，线程安全）
            await websocket.send_text(json.dumps(twin_state))
            # 维持前端60FPS（~16ms）的下发频率，节约算力
            await asyncio.sleep(0.016)

    except WebSocketDisconnect:
        print("Client disconnected")

        

