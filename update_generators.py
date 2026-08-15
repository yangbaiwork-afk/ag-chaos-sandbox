import os
import re

def replace_arm_xml(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    new_arm = """
            <!-- 升级版：多关节仿生机械臂 -->
            <body name="robot_base" pos="0 0 0.1">
                <geom type="cylinder" size="0.1 0.05" rgba="0.5 0.5 0.5 1"/>
                <body name="link1" pos="0 0 0.05">
                    <joint name="joint_yaw" type="hinge" axis="0 0 1" range="-180 180"/>
                    <geom type="sphere" size="0.04" rgba="0.3 0.3 0.3 1"/>

                    <body name="link2" pos="0 0 0.1">
                        <joint name="joint_shoulder" type="hinge" axis="0 1 0" range="-150 150"/>
                        <geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.03" rgba="0.6 0.6 0.6 1"/>

                        <body name="link3" pos="0 0 0.45">
                            <joint name="joint_elbow" type="hinge" axis="0 1 0" range="-150 150"/>
                            <geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.025" rgba="0.6 0.6 0.6 1"/>

                            <geom name="end_effector" type="sphere" pos="0 0 0.45" size="0.05" rgba="0.7 0.7 0.7 1"/>
                        </body>
                    </body>
                </body>
            </body>
"""
    # Replace the old arm
    pattern = r'<!-- 升级版：3DOF 炮台式伸缩机械臂.*?</body>\n\s*</body>\n\s*</body>\n\s*</body>'
    new_content = re.sub(pattern, new_arm.strip(), content, flags=re.DOTALL)

    with open(filepath, 'w') as f:
        f.write(new_content)

for level in ['level1', 'level2', 'level3']:
    replace_arm_xml(f'src/ag_chaos_sandbox/levels/{level}/generator.py')
