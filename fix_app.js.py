with open('src/ag_chaos_sandbox/static/app.js', 'r') as f:
    content = f.read()

# Replace the specific hardcoded 3 with 4, as there are now 5 points (index 4 is the end effector)
content = content.replace("this.eeMesh.position.copy(points[3]);", "this.eeMesh.position.copy(points[4]);")
content = content.replace("this.armDir.subVectors(points[3], points[2]).normalize();", "this.armDir.subVectors(points[4], points[3]).normalize();")

with open('src/ag_chaos_sandbox/static/app.js', 'w') as f:
    f.write(content)
