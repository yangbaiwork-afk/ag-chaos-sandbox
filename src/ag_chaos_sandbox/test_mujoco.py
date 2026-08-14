import mujoco
import mujoco.viewer
import time
import math

# 1. 加载极简物理模型
xml_path = "sandbox_env.xml"
model = mujoco.MjModel.from_xml_path(xml_path)
data = mujoco.MjData(model)

# 找到传感器的 ID，用于后续读取
sensor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "flower_collision")

print("启动 MuJoCo 物理引擎...")

# 2. 启动原生查看器 (仅用于我们自己 Debug 后台骨架)
with mujoco.viewer.launch_passive(model, data) as viewer:
    
    start_time = time.time()
    hp = 100
    
    while viewer.is_running():
        step_start = time.time()
        t = time.time() - start_time

        # --- A. 注入强制运动学控制 (模拟错误指令) ---
        # 让机械臂像扫雷一样来回扫动，故意让它切入花序的坐标
        data.qpos[0] = math.sin(t) * 1.5  # 根关节旋转
        data.qpos[1] = 0.2                # 保持一定高度
        
        # --- B. 物理步进推演 ---
        mujoco.mj_step(model, data)
        
        # --- C. 幽灵传感器逻辑判定 ---
        # 读取 touch 传感器的数据 (只要末端执行器切入 Site，值就会 > 0)
        collision_force = data.sensordata[sensor_id]
        
        if collision_force > 0:
            hp -= 1  # 只要重叠就持续掉血
            print(f"⚠️ [警告] 发生空间穿透！触发农学损伤！当前 HP: {hp}")
            
            if hp <= 0:
                print("💀 番茄花序已彻底损毁。")
                break
                
        # 同步画面
        viewer.sync()

        # 保证仿真时钟与真实时间大致对齐 (60Hz 左右视觉刷新即可)
        time_until_next_step = model.opt.timestep - (time.time() - step_start)
        if time_until_next_step > 0:
            time.sleep(time_until_next_step)