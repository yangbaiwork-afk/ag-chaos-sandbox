with open('src/ag_chaos_sandbox/main.py', 'r') as f:
    content = f.read()

old_skeleton_code = """        j_yaw = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_yaw")
        j_pitch = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_pitch")
        ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
        ee_pos = data.geom_xpos[ee_id]

        twin_state[env_type]["arm_skeleton"] = [
            [0.0, 0.0, 0.1],
            [float(data.xanchor[j_yaw][0]), float(data.xanchor[j_yaw][1]), float(data.xanchor[j_yaw][2])],
            [float(data.xanchor[j_pitch][0]), float(data.xanchor[j_pitch][1]), float(data.xanchor[j_pitch][2])],
            [float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])]
        ]"""

new_skeleton_code = """        j_yaw = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_yaw")
        j_shoulder = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_shoulder")
        j_elbow = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "joint_elbow")
        ee_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "end_effector")
        ee_pos = data.geom_xpos[ee_id]

        twin_state[env_type]["arm_skeleton"] = [
            [0.0, 0.0, 0.1],
            [float(data.xanchor[j_yaw][0]), float(data.xanchor[j_yaw][1]), float(data.xanchor[j_yaw][2])],
            [float(data.xanchor[j_shoulder][0]), float(data.xanchor[j_shoulder][1]), float(data.xanchor[j_shoulder][2])],
            [float(data.xanchor[j_elbow][0]), float(data.xanchor[j_elbow][1]), float(data.xanchor[j_elbow][2])],
            [float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])]
        ]"""

content = content.replace(old_skeleton_code, new_skeleton_code)

with open('src/ag_chaos_sandbox/main.py', 'w') as f:
    f.write(content)
