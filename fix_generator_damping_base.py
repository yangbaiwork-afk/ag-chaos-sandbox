import re

for level in ['level1', 'level2', 'level3']:
    filepath = f'src/ag_chaos_sandbox/levels/{level}/generator.py'
    with open(filepath, 'r') as f:
        content = f.read()

    # The problem might be in the mass of the parts, making it unstable.
    # We will add some mass to the links to stabilize it.

    content = content.replace('<geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.03" rgba="0.6 0.6 0.6 1"/>',
                              '<geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.03" rgba="0.6 0.6 0.6 1" mass="1.0"/>')
    content = content.replace('<geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.025" rgba="0.6 0.6 0.6 1"/>',
                              '<geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.025" rgba="0.6 0.6 0.6 1" mass="1.0"/>')
    content = content.replace('<geom name="end_effector" type="sphere" pos="0 0 0.45" size="0.05" rgba="0.7 0.7 0.7 1"/>',
                              '<geom name="end_effector" type="sphere" pos="0 0 0.45" size="0.05" rgba="0.7 0.7 0.7 1" mass="0.5"/>')

    with open(filepath, 'w') as f:
        f.write(content)
