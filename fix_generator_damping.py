import re

for level in ['level1', 'level2', 'level3']:
    filepath = f'src/ag_chaos_sandbox/levels/{level}/generator.py'
    with open(filepath, 'r') as f:
        content = f.read()

    # The issue "Nan, Inf or huge value in QACC at DOF 1. The simulation is unstable"
    # might happen because of the small timestep and the controller trying to move the joints very quickly.
    # Let's add damping and frictionloss to the joints.
    content = content.replace('<joint name="joint_yaw" type="hinge" axis="0 0 1" range="-180 180"/>',
                              '<joint name="joint_yaw" type="hinge" axis="0 0 1" range="-180 180" damping="1.0" frictionloss="0.5"/>')
    content = content.replace('<joint name="joint_shoulder" type="hinge" axis="0 1 0" range="-150 150"/>',
                              '<joint name="joint_shoulder" type="hinge" axis="0 1 0" range="-150 150" damping="1.0" frictionloss="0.5"/>')
    content = content.replace('<joint name="joint_elbow" type="hinge" axis="0 1 0" range="-150 150"/>',
                              '<joint name="joint_elbow" type="hinge" axis="0 1 0" range="-150 150" damping="1.0" frictionloss="0.5"/>')

    with open(filepath, 'w') as f:
        f.write(content)
