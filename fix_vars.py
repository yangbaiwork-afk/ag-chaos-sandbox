with open('src/ag_chaos_sandbox/main.py', 'r') as f:
    content = f.read()

content = content.replace("current_yaw, current_pitch, current_extend = 0.0, 0.0, 0.0",
                          "current_yaw, current_shoulder, current_elbow = 0.0, 0.0, 0.0")

with open('src/ag_chaos_sandbox/main.py', 'w') as f:
    f.write(content)
