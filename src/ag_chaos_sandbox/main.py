import asyncio
import json
import threading
import math
import time
import copy
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import mujoco

from .levels.level1.generator import generate_procedural_plant_xml

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ================= 1. 环境初始化 =================
MJCF_XML, init_tomatoes, init_leaves = generate_procedural_plant_xml()

def create_initial_state():
    return {
        "arm_skeleton": [],
        "plant_structure": {
            "stem_base": [0.6, 0.0, 0.0],
            "tomatoes": copy.deepcopy(init_tomatoes),
            "leaves": copy.deepcopy(init_leaves)
        },
        "tomato_hp": 100,
        "system_status": "System Normal",
        "active_action": "None",
        "current_target_dist": 0.0,
        "last_damage_time": 0.0
    }

twin_state = {
    "env_no_rules": create_initial_state(),
    "env_rules": create_initial_state()
}

action_queue = []

def load_rules():
    rules_path = Path(__file__).resolve().parent / "levels" / "level1" / "rules.json"
    with open(rules_path, "r") as f:
        return json.load(f)

# ================= 2. 物理引擎与逻辑 =================
def run_simulation(env_type: str, model_xml: str, with_rules: bool):
    global twin_state, action_queue
    print(f"[后台] 启动程序化农业物理引擎 ({env_type})...")

    model = mujoco.MjModel.from_xml_string(model_xml)
    data = mujoco.MjData(model)

    start_time = time.time()

    current_yaw = 0.0
    current_pitch = 0.0
    current_extend = 0.0
    active_target_idx = -1

    ontology_rules = load_rules() if with_rules else {}

    local_action_queue = []
    last_global_queue_len = 0

    while True:
        step_start = time.time()

        # 同步全局队列
        current_global_len = len(action_queue)
        if current_global_len > last_global_queue_len:
            for i in range(last_global_queue_len, current_global_len):
                local_action_queue.append(action_queue[i])
            last_global_queue_len = current_global_len

        # --- A. 指令解析与规则拦截 ---
        if len(local_action_queue) > 0:
            cmd = local_action_queue.pop(0)

            if cmd.startswith("Target:"):
                active_target_idx = int(cmd.split(":")[1])
                twin_state[env_type]["system_status"] = f"Aiming at Target {active_target_idx}..." if active_target_idx != -1 else "Returning Home..."

            elif cmd in ["Cut", "Spray"]:
                if active_target_idx == -1:
                    twin_state[env_type]["system_status"] = "❌ 动作被拦截：未锁定任何目标！" if with_rules else "❌ 执行失败：未锁定任何目标！"
                else:
                    ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
                    ee_pos = data.geom_xpos[ee_id]
                    tx, ty, tz = data.geom_xpos[
                        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
                    dist = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)

                    twin_state[env_type]["current_target_dist"] = dist

                    if with_rules:
                        # 实验组：有规则保护
                        if cmd == "Cut":
                            if dist < ontology_rules["Cut"]["min_safe_dist"]:
                                twin_state[env_type]["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过近，存在剪碎果实风险！"
                            elif dist > ontology_rules["Cut"]["max_effective_dist"]:
                                twin_state[env_type]["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过远，剪刀够不到病叶！"
                            else:
                                twin_state[env_type]["active_action"] = "Cut"
                                twin_state[env_type]["system_status"] = "✂️ 剪除成功！成功去除遮挡叶片，HP +5"
                                twin_state[env_type]["tomato_hp"] = min(100, twin_state[env_type]["tomato_hp"] + 5)
                        elif cmd == "Spray":
                            if dist < ontology_rules["Spray"]["min_effective_dist"]:
                                twin_state[env_type]["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过近，高压水柱会造成物理损伤！"
                            elif dist > ontology_rules["Spray"]["max_effective_dist"]:
                                twin_state[env_type]["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过远，雾化药液已飘散！"
                            else:
                                twin_state[env_type]["active_action"] = "Spray"
                                twin_state[env_type]["system_status"] = "💦 喷洒成功！药液均匀覆盖，HP +10"
                                twin_state[env_type]["tomato_hp"] = min(100, twin_state[env_type]["tomato_hp"] + 10)
                    else:
                        # 对照组：无规则，强行执行
                        twin_state[env_type]["active_action"] = cmd
                        if cmd == "Cut":
                            twin_state[env_type]["system_status"] = f"✂️ 强行剪除 (距离 {dist * 100:.1f}cm)"
                            if dist >= 0.10 and dist <= 0.15:
                                twin_state[env_type]["tomato_hp"] = min(100, twin_state[env_type]["tomato_hp"] + 5)
                        elif cmd == "Spray":
                            twin_state[env_type]["system_status"] = f"💦 强行喷洒 (距离 {dist * 100:.1f}cm)"
                            if dist >= 0.15 and dist <= 0.30:
                                twin_state[env_type]["tomato_hp"] = min(100, twin_state[env_type]["tomato_hp"] + 10)

                    # 动作后摇表现 (1秒)
                    if twin_state[env_type]["active_action"] != "None":
                        def clear_action(env=env_type):
                            twin_state[env]["active_action"] = "None"
                        threading.Timer(1.0, clear_action).start()

        # --- B. 逆运动学 (IK) 寻迹 ---
        target_yaw, target_pitch, target_extend = 0.0, 0.0, 0.0

        if active_target_idx >= 0:
            tx, ty, tz = data.geom_xpos[
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
            target_yaw = math.atan2(ty, tx)
            xy_distance = math.hypot(tx, ty)
            target_pitch = -math.atan2(tz - 0.15, xy_distance)
            target_extend = math.hypot(xy_distance, tz - 0.15) - 0.5  # 扣除基础连杆长度

        # P-控制器平滑过渡
        current_yaw += (target_yaw - current_yaw) * 0.05
        current_pitch += (target_pitch - current_pitch) * 0.05
        current_extend += (target_extend - current_extend) * 0.05

        data.qpos[0] = current_yaw
        data.qpos[1] = current_pitch
        data.qpos[2] = current_extend

        mujoco.mj_step(model, data)

        # --- C. 骨架提取 & 雷达测距同步 ---
        j_yaw = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_yaw")
        j_pitch = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_pitch")
        ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
        ee_pos = data.geom_xpos[ee_id]

        twin_state[env_type]["arm_skeleton"] = [
            [0.0, 0.0, 0.1],
            [float(data.xanchor[j_yaw][0]), float(data.xanchor[j_yaw][1]), float(data.xanchor[j_yaw][2])],
            [float(data.xanchor[j_pitch][0]), float(data.xanchor[j_pitch][1]), float(data.xanchor[j_pitch][2])],
            [float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])]
        ]

        if active_target_idx != -1 and twin_state[env_type]["active_action"] == "None":
            tx, ty, tz = data.geom_xpos[
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
            twin_state[env_type]["current_target_dist"] = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)
        elif active_target_idx == -1:
            twin_state[env_type]["current_target_dist"] = 0.0

        # --- D. 物理碰撞监测 (无敌帧冷却逻辑) ---
        if active_target_idx >= 0:
            tx, ty, tz = data.geom_xpos[
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
            distance = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)

            curr_t = time.time()
            if distance < 0.08 and (curr_t - twin_state[env_type].get("last_damage_time", 0)) > 1.5:
                if twin_state[env_type]["tomato_hp"] > 0:
                    twin_state[env_type]["tomato_hp"] -= 15
                    twin_state[env_type]["last_damage_time"] = curr_t
                    twin_state[env_type]["system_status"] = "CRITICAL: Physical Collision! (-15 HP)"
            elif distance >= 0.08 and (curr_t - twin_state[env_type].get("last_damage_time", 0)) > 1.5:
                if twin_state[env_type]["active_action"] == "None" and not twin_state[env_type]["system_status"].startswith("Aiming"):
                    twin_state[env_type]["system_status"] = "System Normal"

        # 锁频维持仿真流速
        time_util_next = model.opt.timestep - (time.time() - step_start)
        if time_util_next > 0:
            time.sleep(time_util_next)

# 启动双物理引擎线程
threading.Thread(target=run_simulation, args=("env_no_rules", MJCF_XML, False), daemon=True).start()
threading.Thread(target=run_simulation, args=("env_rules", MJCF_XML, True), daemon=True).start()

# ================= 3. 全双工 WebSocket =================
@app.get("/")
async def get_index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[网络] 前端数字孪生面板已连接")

    async def receive_commands():
        try:
            while True:
                data = await websocket.receive_text()
                action_queue.append(data)
        except WebSocketDisconnect:
            pass

    async def send_state():
        try:
            while True:
                await websocket.send_text(json.dumps(twin_state))
                await asyncio.sleep(0.016)
        except WebSocketDisconnect:
            pass

    await asyncio.gather(receive_commands(), send_state())
