import re
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
from .levels.level3.generator import generate_procedural_plant_xml as generate_level3_xml

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ================= 0. 日志系统初始化 =================
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_LOG_FILE = LOGS_DIR / "session_results.jsonl"

# 全局存储当前活跃学生的姓名
current_student_name = "Anonymous"

def evaluate_score(hps: list) -> dict:
    perfect = sum(1 for hp in hps if hp == 100)
    good = sum(1 for hp in hps if 80 <= hp < 100)
    damaged = sum(1 for hp in hps if hp < 80)
    total_score = sum(hps) / len(hps) if hps else 0
    return {
        "perfect_tomatoes": perfect,
        "good_tomatoes": good,
        "damaged_tomatoes": damaged,
        "total_score": round(total_score, 1)
    }

def save_session_result(session_id: str):
    """保存本次会话的最终多维度状态，供教师评分使用"""
    global twin_state, current_student_name

    no_rules_hps = twin_state["env_no_rules"].get("tomato_hps", [])
    rules_hps = twin_state["env_rules"].get("tomato_hps", [])

    record = {
        "timestamp": time.time(),
        "session_id": session_id,
        "student_name": current_student_name,
        "env_no_rules_result": evaluate_score(no_rules_hps),
        "env_rules_result": evaluate_score(rules_hps)
    }
    with open(SESSION_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# ================= 1. 环境初始化 =================
LEVEL_MODELS = {
    "level1": generate_procedural_plant_xml(),
    "level2": generate_procedural_plant_xml(),
    "level3": generate_level3_xml()
}
MJCF_XML = LEVEL_MODELS["level1"][0]
init_tomatoes = LEVEL_MODELS["level1"][1]
init_leaves = LEVEL_MODELS["level1"][2]

def create_initial_state():
    return {
        "arm_skeleton": [],
        "plant_structure": {
            "stem_base": [0.6, 0.0, 0.0],
            "tomatoes": copy.deepcopy(init_tomatoes),
            "leaves": copy.deepcopy(init_leaves),
            "diseased_leaves": LEVEL_MODELS.get("level3", (None, None, None, []))[3] if "level3" in LEVEL_MODELS else []
        },
        "tomato_hps": [100] * len(init_tomatoes),
        "system_status": "System Normal",
        "active_action": "None",
        "current_target_dist": 0.0,
        "last_damage_times": [0.0] * len(init_tomatoes),
        "wind_speed": 0.0,
        "current_level": "level1"
    }

twin_state = {
    "env_no_rules": create_initial_state(),
    "env_rules": create_initial_state(),
    "rules_config": None
}

action_queue = []

def load_rules(level: str = "level1"):
    rules_path = Path(__file__).resolve().parent / "levels" / level / "rules.json"
    if not rules_path.exists():
        # Fallback to level1 if missing
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
    current_shoulder = 0.0
    current_elbow = 0.0
    active_target_idx = -1

    current_level = "level1"
    ontology_rules = load_rules(current_level) if with_rules else {}

    # 初始化前端绑定的规则（仅让 env_rules 负责上传一次给前端）
    if with_rules:
        twin_state["rules_config"] = ontology_rules

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

            if cmd.startswith("Student:"):
                # Handle it only in one thread to avoid redundant global assignments
                if env_type == "env_rules":
                    global current_student_name
                    current_student_name = cmd.split(":", 1)[1]
                continue

            elif cmd.startswith("UpdateRules:"):
                if env_type == "env_rules":
                    try:
                        new_rules_str = cmd.split(":", 1)[1]
                        ontology_rules = json.loads(new_rules_str)
                        twin_state["rules_config"] = ontology_rules
                    except Exception as e:
                        print(f"Failed to update rules: {e}")
                continue

            elif cmd.startswith("SetLevel:"):
                current_level = cmd.split(":", 1)[1]
                twin_state[env_type]["current_level"] = current_level
                if with_rules:
                    ontology_rules = load_rules(current_level)
                    twin_state["rules_config"] = ontology_rules

                # Dynamically load the new level's model into the engine
                new_xml = LEVEL_MODELS.get(current_level, LEVEL_MODELS["level1"])[0]
                model = mujoco.MjModel.from_xml_string(new_xml)
                data = mujoco.MjData(model)
                active_target_idx = -1

                old_wind = twin_state[env_type]["wind_speed"]
                twin_state[env_type] = create_initial_state()
                if current_level == "level3":
                    twin_state[env_type]["plant_structure"]["tomatoes"] = LEVEL_MODELS["level3"][1]
                    twin_state[env_type]["plant_structure"]["leaves"] = LEVEL_MODELS["level3"][2]
                    twin_state[env_type]["plant_structure"]["diseased_leaves"] = LEVEL_MODELS["level3"][3]
                twin_state[env_type]["current_level"] = current_level
                twin_state[env_type]["wind_speed"] = old_wind

                twin_state[env_type]["active_target_name"] = None
                continue

            elif cmd.startswith("SetWind:"):
                try:
                    wind_speed = float(cmd.split(":", 1)[1])
                    twin_state[env_type]["wind_speed"] = wind_speed
                except Exception:
                    pass
                continue

            elif cmd == "Reset":
                # Only save log once per reset (avoid duplicate log from two env threads)
                if env_type == "env_rules":
                    save_session_result(f"reset_{int(time.time())}")

                old_level = twin_state[env_type]["current_level"]
                old_wind = twin_state[env_type]["wind_speed"]

                twin_state[env_type] = create_initial_state()
                twin_state[env_type]["current_level"] = old_level
                twin_state[env_type]["wind_speed"] = old_wind

                active_target_idx = -1
                current_yaw = 0.0
                current_shoulder = 0.0
                current_elbow = 0.0
                continue

            elif cmd.startswith("Target:"):
                target_str = cmd.split(":", 1)[1]
                if target_str.isdigit() or target_str == "-1":
                    idx = int(target_str)
                    if idx == -1:
                        active_target_name = None
                        active_target_idx = -1
                    else:
                        active_target_name = f"tomato_{idx}"
                        active_target_idx = idx
                else:
                    active_target_name = target_str
                    m_idx = re.search(r'_(\d+)$', target_str)
                    active_target_idx = int(m_idx.group(1)) if m_idx else -1

                twin_state[env_type]["system_status"] = f"Aiming at {active_target_name}..." if active_target_name else "Returning Home..."
                twin_state[env_type]["active_target_name"] = active_target_name

            elif cmd in ["Cut", "Spray"]:
                active_target_name = twin_state[env_type].get("active_target_name")
                if not active_target_name:
                    twin_state[env_type]["system_status"] = "❌ 动作被拦截：未锁定任何目标！" if with_rules else "❌ 执行失败：未锁定任何目标！"
                else:
                    ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
                    ee_pos = data.geom_xpos[ee_id]

                    try:
                        target_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, active_target_name)
                        tx, ty, tz = data.geom_xpos[target_id]
                    except Exception:
                        twin_state[env_type]["system_status"] = "❌ 找不到目标"
                        continue

                    dist = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)
                    twin_state[env_type]["current_target_dist"] = dist

                    is_tomato = "tomato" in active_target_name
                    is_healthy_leaf = "leaf" in active_target_name and "diseased" not in active_target_name
                    is_diseased_leaf = "diseased_leaf" in active_target_name

                    target_tomato_idx = active_target_idx if is_tomato else -1

                    has_occlusion = False
                    if current_level == "level3" and is_tomato:
                        if len(twin_state[env_type]["plant_structure"].get("diseased_leaves", [])) > 0:
                             has_occlusion = True

                    if with_rules:
                        if cmd == "Cut":
                            forbidden = ontology_rules.get("Cut", {}).get("forbidden_targets", [])
                            allowed = ontology_rules.get("Cut", {}).get("allowed_targets", [])
                            target_type_general = "tomato" if is_tomato else "healthy_leaf" if is_healthy_leaf else "diseased_leaf" if is_diseased_leaf else "unknown"

                            if target_type_general in forbidden or (allowed and target_type_general not in allowed):
                                twin_state[env_type]["system_status"] = f"❌ 拦截：不能修剪 {target_type_general}！"
                            elif dist > ontology_rules.get("Cut", {}).get("max_effective_dist", 0.20):
                                twin_state[env_type]["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过远，剪刀够不到！"
                            else:
                                twin_state[env_type]["active_action"] = "Cut"
                                twin_state[env_type]["system_status"] = f"✂️ 剪除成功！成功去除 {active_target_name}"
                                if is_diseased_leaf:
                                    if len(twin_state[env_type]["plant_structure"]["diseased_leaves"]) > active_target_idx:
                                        twin_state[env_type]["plant_structure"]["diseased_leaves"].pop(active_target_idx)
                                        twin_state[env_type]["active_target_name"] = None
                                        # Tell frontend to redraw plant structure
                                        twin_state[env_type]["plant_structure_updated"] = True

                        elif cmd == "Spray":
                            wind_speed = twin_state[env_type].get("wind_speed", 0.0)
                            max_wind = ontology_rules.get("Spray", {}).get("max_wind_speed", float('inf'))
                            reqs = ontology_rules.get("Spray", {}).get("requires", [])

                            if "Path_Clearance" in reqs and has_occlusion:
                                twin_state[env_type]["system_status"] = "❌ 拦截：路径被遮挡，无法安全到达！需先执行修剪。"
                            elif "No_Occlusion" in reqs and has_occlusion:
                                twin_state[env_type]["system_status"] = "❌ 拦截：有病叶遮挡，无法喷洒！需先执行修剪。"
                            elif wind_speed > max_wind:
                                twin_state[env_type]["system_status"] = f"❌ 拦截：风速 ({wind_speed} m/s) 过高，存在药液漂移风险！"
                            elif dist > ontology_rules.get("Spray", {}).get("max_effective_dist", 0.35):
                                twin_state[env_type]["system_status"] = f"❌ 拦截：距离 ({dist * 100:.1f}cm) 过远，雾化药液已飘散！"
                            else:
                                twin_state[env_type]["active_action"] = "Spray"
                                twin_state[env_type]["system_status"] = "💦 喷洒成功！"
                                if is_tomato and target_tomato_idx >= 0:
                                    twin_state[env_type]["tomato_hps"][target_tomato_idx] = min(100, twin_state[env_type]["tomato_hps"][target_tomato_idx] + 10)

                    else:
                        twin_state[env_type]["active_action"] = cmd
                        if cmd == "Cut":
                            twin_state[env_type]["system_status"] = f"✂️ 强行剪除 {active_target_name} (距离 {dist * 100:.1f}cm)"
                            if is_tomato and target_tomato_idx >= 0:
                                twin_state[env_type]["tomato_hps"][target_tomato_idx] -= 50
                                twin_state[env_type]["system_status"] = "❌ 药害！剪碎了番茄 (-50 HP)"
                            elif is_diseased_leaf:
                                if len(twin_state[env_type]["plant_structure"]["diseased_leaves"]) > active_target_idx:
                                    twin_state[env_type]["plant_structure"]["diseased_leaves"].pop(active_target_idx)
                                    twin_state[env_type]["active_target_name"] = None
                                    twin_state[env_type]["plant_structure_updated"] = True
                        elif cmd == "Spray":
                            wind_speed = twin_state[env_type].get("wind_speed", 0.0)
                            if wind_speed > 5.0:
                                twin_state[env_type]["system_status"] = "⚠️ 药害！风速过大 (-15 HP)"
                                if is_tomato and target_tomato_idx >= 0:
                                    twin_state[env_type]["tomato_hps"][target_tomato_idx] -= 15
                            elif has_occlusion:
                                twin_state[env_type]["system_status"] = "⚠️ 喷洒被遮挡，效果差 (-10 HP)"
                                if is_tomato and target_tomato_idx >= 0:
                                    twin_state[env_type]["tomato_hps"][target_tomato_idx] -= 10
                            else:
                                twin_state[env_type]["system_status"] = f"💦 强行喷洒 {active_target_name} (距离 {dist * 100:.1f}cm)"
                                if is_tomato and target_tomato_idx >= 0:
                                    twin_state[env_type]["tomato_hps"][target_tomato_idx] = min(100, twin_state[env_type]["tomato_hps"][target_tomato_idx] + 10)

                    if twin_state[env_type]["active_action"] != "None":
                        def clear_action(env=env_type):
                            twin_state[env]["active_action"] = "None"
                        threading.Timer(1.0, clear_action).start()

        # --- B. 逆运动学 (IK) 寻迹 (多关节仿生臂) ---
        target_yaw, target_shoulder, target_elbow = 0.0, 0.0, 0.0

        active_target_name = twin_state[env_type].get("active_target_name")
        if active_target_name:
            try:
                target_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, active_target_name)
                tx, ty, tz = data.geom_xpos[target_id]
            except Exception:
                tx, ty, tz = 0.0, 0.0, 0.15

            if with_rules:
                standoff = ontology_rules.get("Target", {}).get("safe_standoff", 0.13)
            else:
                standoff = 0.03

            # Apply standoff along the vector from origin to target (simplified)
            dist_to_target = math.hypot(tx, ty, tz - 0.1) # approx distance from base
            if dist_to_target > 0:
                tx_standoff = tx - (tx / dist_to_target) * standoff
                ty_standoff = ty - (ty / dist_to_target) * standoff
                tz_standoff = tz - ((tz - 0.1) / dist_to_target) * standoff
            else:
                tx_standoff, ty_standoff, tz_standoff = tx, ty, tz

            # IK Calculation for 3-link arm
            l1, l2, l3 = 0.05, 0.45, 0.45
            base_z = 0.1

            rx = tx_standoff
            ry = ty_standoff
            rz = tz_standoff - base_z

            yaw = math.atan2(ry, rx)

            shoulder_z = l1
            r = math.hypot(rx, ry)
            dz = rz - shoulder_z
            d = math.hypot(r, dz)

            max_reach = l2 + l3 - 1e-4
            if d > max_reach:
                d = max_reach

            cos_elbow = (d**2 - l2**2 - l3**2) / (2 * l2 * l3)
            cos_elbow = max(-1.0, min(1.0, cos_elbow))
            elbow = math.acos(cos_elbow)

            alpha = math.atan2(dz, r)
            cos_shoulder = (l2**2 + d**2 - l3**2) / (2 * l2 * d)
            cos_shoulder = max(-1.0, min(1.0, cos_shoulder))
            beta = math.acos(cos_shoulder)

            shoulder = math.pi/2 - (alpha + beta)

            target_yaw = yaw
            target_shoulder = shoulder
            target_elbow = elbow

            # Simplified collision check logic
            if not with_rules and d >= max_reach * 0.9:
                if current_level == "level3" and "diseased_leaf" not in active_target_name:
                    if time.time() - twin_state[env_type].get("last_collision_time", 0) > 2.0:
                        is_t = "tomato" in active_target_name
                        m_idx = re.search(r'_(\d+)$', active_target_name)
                        t_idx = int(m_idx.group(1)) if (is_t and m_idx) else -1
                        if is_t and t_idx >= 0 and twin_state[env_type]["tomato_hps"][t_idx] > 0:
                            twin_state[env_type]["tomato_hps"][t_idx] -= 15
                            twin_state[env_type]["system_status"] = "💥 碰撞警报！机械臂靠太近戳伤目标 (-15 HP)"
                            twin_state[env_type]["last_collision_time"] = time.time()

        # P-控制器平滑过渡
        current_yaw += (target_yaw - current_yaw) * 0.05
        current_shoulder += (target_shoulder - current_shoulder) * 0.05
        current_elbow += (target_elbow - current_elbow) * 0.05

        j_yaw = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_yaw")
        j_shoulder = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_shoulder")
        j_elbow = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_elbow")

        if j_yaw >= 0: data.qpos[model.jnt_qposadr[j_yaw]] = current_yaw
        if j_shoulder >= 0: data.qpos[model.jnt_qposadr[j_shoulder]] = current_shoulder
        if j_elbow >= 0: data.qpos[model.jnt_qposadr[j_elbow]] = current_elbow

        mujoco.mj_step(model, data)

        # --- C. 骨架提取 & 雷达测距同步 ---


        ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
        ee_pos = data.geom_xpos[ee_id]

        twin_state[env_type]["arm_skeleton"] = [
            [0.0, 0.0, 0.1],
            [float(data.xanchor[j_yaw][0]), float(data.xanchor[j_yaw][1]), float(data.xanchor[j_yaw][2])],
            [float(data.xanchor[j_shoulder][0]), float(data.xanchor[j_shoulder][1]), float(data.xanchor[j_shoulder][2])],
            [float(data.xanchor[j_elbow][0]), float(data.xanchor[j_elbow][1]), float(data.xanchor[j_elbow][2])],
            [float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])]
        ]

        if active_target_idx != -1 and twin_state[env_type]["active_action"] == "None":
            tx, ty, tz = data.geom_xpos[
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{active_target_idx}")]
            twin_state[env_type]["current_target_dist"] = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)
        elif active_target_idx == -1:
            twin_state[env_type]["current_target_dist"] = 0.0

        # --- D. 物理碰撞监测 (无敌帧冷却逻辑) ---
        is_t = active_target_name and "tomato" in active_target_name
        m_idx = re.search(r'_(\d+)$', active_target_name) if active_target_name else None
        t_idx = int(m_idx.group(1)) if (is_t and m_idx) else -1

        if t_idx >= 0 and not with_rules:
            try:
                tx, ty, tz = data.geom_xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"tomato_{t_idx}")]
                distance = math.hypot(ee_pos[0] - tx, ee_pos[1] - ty, ee_pos[2] - tz)

                curr_t = time.time()
                last_dmg_times = twin_state[env_type].get("last_damage_times", [])

                if distance < 0.08 and (curr_t - last_dmg_times[t_idx]) > 1.5:
                    if twin_state[env_type]["tomato_hps"][t_idx] > 0:
                        twin_state[env_type]["tomato_hps"][t_idx] -= 15
                        twin_state[env_type]["last_damage_times"][t_idx] = curr_t
                        if not twin_state[env_type]["system_status"].startswith("❌"):
                            twin_state[env_type]["system_status"] = f"CRITICAL: Collision on Tomato {t_idx}! (-15 HP)"
                elif distance >= 0.08 and (curr_t - last_dmg_times[t_idx]) > 1.5:
                    if twin_state[env_type]["active_action"] == "None" and not twin_state[env_type]["system_status"].startswith("Aiming") and not twin_state[env_type]["system_status"].startswith("❌"):
                        twin_state[env_type]["system_status"] = "System Normal"
            except Exception:
                pass
        elif with_rules and active_target_name:
            if twin_state[env_type]["active_action"] == "None" and not twin_state[env_type]["system_status"].startswith("Aiming") and not twin_state[env_type]["system_status"].startswith("❌"):
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

    # 生成唯一连接ID
    session_id = f"conn_{id(websocket)}_{int(time.time())}"

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

    try:
        await asyncio.gather(receive_commands(), send_state())
    except Exception as e:
        print(f"WebSocket closed: {e}")
    finally:
        save_session_result(session_id)
