with open('src/ag_chaos_sandbox/main.py', 'r') as f:
    content = f.read()

# I see it was originally defined as:
# current_yaw = 0.0
# current_pitch = 0.0
# current_extend = 0.0

content = content.replace("current_yaw = 0.0\n    current_pitch = 0.0\n    current_extend = 0.0",
                          "current_yaw = 0.0\n    current_shoulder = 0.0\n    current_elbow = 0.0")

content = content.replace("current_yaw = 0.0\n                current_pitch = 0.0\n                current_extend = 0.0",
                          "current_yaw = 0.0\n                current_shoulder = 0.0\n                current_elbow = 0.0")

with open('src/ag_chaos_sandbox/main.py', 'w') as f:
    f.write(content)
