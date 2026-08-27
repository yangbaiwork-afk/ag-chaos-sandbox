import math
import random

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

    xml_parts = ["
    <mujoco model="ag_chaos_sandbox_v2">
        <compiler angle="degree" coordinate="local"/>
        <option gravity="0 0 -9.81" timestep="0.002"/>
        <worldbody>
            <light pos="0 0 3" dir="0 0 -1"/>
            <geom type="plane" size="2 2 0.1" rgba="0.9 0.9 0.9 1"/>

            <!-- 升级版：多关节仿生机械臂 -->
            <body name="robot_base" pos="0 0 0.1">
                <geom type="cylinder" size="0.1 0.05" rgba="0.5 0.5 0.5 1"/>
                <body name="link1" pos="0 0 0.05">
                    <joint name="joint_yaw" type="hinge" axis="0 0 1" range="-180 180" damping="1.0" frictionloss="0.5"/>
                    <geom type="sphere" size="0.04" rgba="0.3 0.3 0.3 1"/>

                    <body name="link2" pos="0 0 0.1">
                        <joint name="joint_shoulder" type="hinge" axis="0 1 0" range="-150 150" damping="1.0" frictionloss="0.5"/>
                        <geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.03" rgba="0.6 0.6 0.6 1" mass="1.0"/>

                        <body name="link3" pos="0 0 0.45">
                            <joint name="joint_elbow" type="hinge" axis="0 1 0" range="-150 150" damping="1.0" frictionloss="0.5"/>
                            <geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.025" rgba="0.6 0.6 0.6 1" mass="1.0"/>

                            <geom name="end_effector" type="sphere" pos="0 0 0.45" size="0.05" rgba="0.7 0.7 0.7 1" mass="0.5"/>
                        </body>
                    </body>
                </body>
            </body>

            <!-- 植物主茎 -->
            <body name="main_stem" pos="0.6 0 0">
                <geom type="cylinder" size="0.02 0.3" pos="0 0 0.3" rgba="0.2 0.8 0.2 1" />
    """]

    # 动态插入番茄
    for i, t in enumerate(tomatoes):
        xml_parts.append(f'<geom name="tomato_{i}" type="sphere" size="0.04" pos="{t[0]} {t[1]} {t[2]}" rgba="1 0.2 0.2 1" contype="0" conaffinity="0"/>\n')

    # 动态插入叶片
    for i, leaf in enumerate(leaves):
        xml_parts.append(f'<geom name="leaf_{i}" type="ellipsoid" size="0.06 0.04 0.01" pos="{leaf[0]} {leaf[1]} {leaf[2]}" rgba="0.1 0.6 0.1 1" contype="0" conaffinity="0"/>\n')

    xml_parts.append("""
            </body>
        </worldbody>
    </mujoco>
    """)
    return "".join(xml_parts), tomatoes, leaves
