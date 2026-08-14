import asyncio
import json
import threading
import math
import time
import random
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import mujoco

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ================= 1. 程序化植物生成器 =================
def generate_procedural_plant_xml():
    """动态生成带有随机叶片和番茄的 MuJoCo XML 以及升级版 3DOF 机械臂"""
    tomatoes = []
    leaves = []

    # 随机生成 3 个番茄
    for _ in range(3):
        h = random.uniform(0.2, 0.5)
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.1, 0.2)
        tomatoes.append([r * math.cos(angle), r * math.sin(angle), h])

    # 随机生成 5 片叶子
    for _ in range(5):
        h = random.uniform(0.1, 0.6)
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.05, 0.15)
        leaves.append([r * math.cos(angle), r * math.sin(angle), h])

    xml_str = f"""
    <mujoco model="ag_chaos_sandbox_v2">
        <compiler angle="degree" coordinate="local"/>
        <option gravity="0 0 -9.81" timestep="0.002"/>
        <worldbody>
            <light pos="0 0 3" dir="0 0 -1"/>
            <geom type="plane" size="2 2 0.1" rgba="0.9 0.9 0.9 1"/>

            <!-- 升级版：3DOF 炮台式伸缩机械臂 (已修复质量为 0 的 Bug) -->
            <body name="robot_base" pos="0 0 0.1">
                <geom type="cylinder" size="0.1 0.05" rgba="0.5 0.5 0.5 1"/>
                <body name="yaw_link" pos="0 0 0.05">
                    <joint name="joint_yaw" type="hinge" axis="0 0 1" range="-180 180"/>
                    <!-- 【修复】加一个小球赋予偏航关节质量 -->
                    <geom type="sphere" size="0.04" rgba="0.3 0.3 0.3 1"/> 
                    
                    <body name="pitch_link" pos="0 0 0">
                        <joint name="joint_pitch" type="hinge" axis="0 1 0" range="-90 90"/>
                        <!-- 【修复】加一个小球赋予俯仰关节质量 -->
                        <geom type="sphere" size="0.04" rgba="0.3 0.3 0.3 1"/> 
                        
                        <body name="arm_boom" pos="0 0 0">
                            <!-- 直线伸缩关节 -->
                            <joint name="joint_extend" type="slide" axis="1 0 0" range="-0.5 1.5"/>
                            <geom type="capsule" fromto="0 0 0 0.5 0 0" size="0.02" rgba="0.6 0.6 0.6 1"/>
                            <geom name="end_effector" type="sphere" pos="0.5 0 0" size="0.05" rgba="0.7 0.7 0.7 1"/>
                        </body>
                    </body>
                </body>
            </body>

            <!-- 植物主茎 -->
            <body name="main_stem" pos="0.6 0 0">
                <geom type="cylinder" size="0.02 0.3" pos="0 0 0.3" rgba="0.2 0.8 0.2 1" />
    """

    # 动态插入番茄
    for i, t in enumerate(tomatoes):
        xml_str += f'<geom name="tomato_{i}" type="sphere" size="0.04" pos="{t[0]} {t[1]} {t[2]}" rgba="1 0.2 0.2 1" contype="0" conaffinity="0"/>\n'

    # 动态插入叶片
    for i, l in enumerate(leaves):
        xml_str += f'<geom name="leaf_{i}" type="ellipsoid" size="0.06 0.04 0.01" pos="{l[0]} {l[1]} {l[2]}" rgba="0.1 0.6 0.1 1" contype="0" conaffinity="0"/>\n'

    xml_str += """
            </body>
        </worldbody>
    </mujoco>
    """
    return xml_str, tomatoes, leaves


# ================= 2. 状态总线与队列 =================
MJCF_XML, init_tomatoes, init_leaves = generate_procedural_plant_xml()

twin_state = {
    "arm_skeleton": [],
    "plant_structure": {
        "stem_base": [0.6, 0.0, 0.0],
        "tomatoes": init_tomatoes,
        "leaves": init_leaves
    },
    "tomato_hp": 100,
    "system_status": "System Normal",
    "active_action": "None",
    "current_target_dist": 0.0,
    "last_damage_time": 0.0
}

action_queue = []


# ================= 3. 物理引擎与拦截防线 =================
def run_physics_engine():
    global twin_state, action_queue
    print("[后台] 启动程序化农业物理引擎...")

    model = mujoco.MjModel.from_xml_string(MJCF_XML)
    data = mujoco.MjData(model)

    start_time = time.time()

    # 内部伺服电机状态
    current_yaw = 0.0
    current_pitch = 0.0
    current_extend = 0.0
    active_target_idx = -1

    # Ontology 本体安全规则 (未来由大一新生编写的 JSON 定义)
    ontology_rules = {
        "Cut": {
            "min_safe_dist": 0.10,
            "max_effective_dist": 0.15
        },
        "Spray": {
            "min_effective_dist": 0.15,
            "max_effective_dist": 0.30
        }
    }

    while True:
        step_start = time.time()

        # --- A. 指令解析与规则拦截 ---
        if len(action_queue) > 0:
            cmd = action_queue.pop(0)

            if cmd.startswith("Target:"):
                active_target_idx = int(cmd.split(":")[1])
                twin_state[
                    "system_status"] = f"Aiming at Target {active_target_idx}..." if active_target_idx != -1 else "Returning Home..."

            elif cmd in ["Cut", "Spray"]:
                if active_target_idx == -1:
                    twin_state["system_status"] = "❌ 动作被拦截：未锁定任何目标！"
                else:
                    # 抓取当前末端与目标的绝对距离
                    ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
                    ee_pos = data.geom_xpos[ee_id]
                    tx, ty, tz = data.geom_xpos[
                        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
                    dist = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)

                    twin_state["current_target_dist"] = dist

                    # 拦截逻辑判定
                    if cmd == "Cut":
                        if dist < ontology_rules["Cut"]["min_safe_dist"]:
                            twin_state["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过近，存在剪碎果实风险！"
                        elif dist > ontology_rules["Cut"]["max_effective_dist"]:
                            twin_state["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过远，剪刀够不到病叶！"
                        else:
                            twin_state["active_action"] = "Cut"
                            twin_state["system_status"] = "✂️ 剪除成功！成功去除遮挡叶片，HP +5"
                            twin_state["tomato_hp"] = min(100, twin_state["tomato_hp"] + 5)

                    elif cmd == "Spray":
                        if dist < ontology_rules["Spray"]["min_effective_dist"]:
                            twin_state[
                                "system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过近，高压水柱会造成物理损伤！"
                        elif dist > ontology_rules["Spray"]["max_effective_dist"]:
                            twin_state["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过远，雾化药液已飘散！"
                        else:
                            twin_state["active_action"] = "Spray"
                            twin_state["system_status"] = "💦 喷洒成功！药液均匀覆盖，HP +10"
                            twin_state["tomato_hp"] = min(100, twin_state["tomato_hp"] + 10)

                    # 动作后摇表现 (1秒)
                    if twin_state["active_action"] != "None":
                        threading.Timer(1.0, lambda: twin_state.update({"active_action": "None"})).start()

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

        twin_state["arm_skeleton"] = [
            [0.0, 0.0, 0.1],
            [float(data.xanchor[j_yaw][0]), float(data.xanchor[j_yaw][1]), float(data.xanchor[j_yaw][2])],
            [float(data.xanchor[j_pitch][0]), float(data.xanchor[j_pitch][1]), float(data.xanchor[j_pitch][2])],
            [float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])]
        ]

        if active_target_idx != -1 and twin_state["active_action"] == "None":
            tx, ty, tz = data.geom_xpos[
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
            twin_state["current_target_dist"] = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)
        elif active_target_idx == -1:
            twin_state["current_target_dist"] = 0.0

        # --- D. 物理碰撞监测 (无敌帧冷却逻辑) ---
        if active_target_idx >= 0:
            tx, ty, tz = data.geom_xpos[
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
            distance = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)

            curr_t = time.time()
            if distance < 0.08 and (curr_t - twin_state.get("last_damage_time", 0)) > 1.5:
                if twin_state["tomato_hp"] > 0:
                    twin_state["tomato_hp"] -= 15
                    twin_state["last_damage_time"] = curr_t
                    twin_state["system_status"] = "CRITICAL: Physical Collision!"
            elif distance >= 0.08 and (curr_t - twin_state.get("last_damage_time", 0)) > 1.5:
                if twin_state["active_action"] == "None" and not twin_state["system_status"].startswith("Aiming"):
                    twin_state["system_status"] = "System Normal"

        # 锁频维持仿真流速
        time_util_next = model.opt.timestep - (time.time() - step_start)
        if time_util_next > 0:
            time.sleep(time_util_next)


threading.Thread(target=run_physics_engine, daemon=True).start()


# ================= 4. 全双工 WebSocket =================
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