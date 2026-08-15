import re

with open('src/ag_chaos_sandbox/main.py', 'r') as f:
    content = f.read()

content = content.replace("current_yaw, current_pitch, current_extend = 0.0, 0.0, 0.0",
                          "current_yaw, current_shoulder, current_elbow = 0.0, 0.0, 0.0")

ik_logic = r"""
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
            target_elbow = -elbow

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

        data.qpos[0] = current_yaw
        data.qpos[1] = current_shoulder
        data.qpos[2] = current_elbow
"""

# Must double escape for regex replace
ik_logic_escaped = ik_logic.replace('\\', '\\\\')

search_pattern = r'# --- B\. 逆运动学 \(IK\) 寻迹 ---.*?data\.qpos\[2\] = current_extend'

content = re.sub(search_pattern, ik_logic_escaped.strip(), content, flags=re.DOTALL)

with open('src/ag_chaos_sandbox/main.py', 'w') as f:
    f.write(content)
