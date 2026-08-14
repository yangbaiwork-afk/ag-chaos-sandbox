# Ag-Chaos Sandbox

一个用于验证农业具身智能（Embodied AI）安全性和鲁棒性的数字孪生教学实验平台。

## 快速启动 (How to Run)

本项目使用 `uv` 进行依赖管理和运行环境管理。

```bash
# 启动 FastAPI 后端与数字孪生服务器
uv run uvicorn ag_chaos_sandbox.main:app --app-dir src --host 127.0.0.1 --port 8765

# 浏览器访问前端可视化面板 (对照组 vs 实验组)
# http://127.0.0.1:8765/
```

## 学生接口与算法接入 (For Students)

学生无需直接操作前端页面，而是通过 WebSocket 编写 Python 自动化脚本，体验真实机器人的控制流。

```python
# 示例：连接服务器并下发指令
import asyncio, websockets, json

async def my_agent():
    async with websockets.connect("ws://localhost:8765/ws") as ws:
        await ws.send("Target:0")  # 瞄准番茄 0
        await asyncio.sleep(2)
        await ws.send("Spray")     # 喷洒

        # 监听状态并做决策...
        state = json.loads(await ws.recv())

asyncio.run(my_agent())
```
*(完整 API 列表与参数说明，请参阅 `tech_spec.md`)*

**参考答案与自动化测试脚本**:
可以运行 `uv run python src/ag_chaos_sandbox/levels/level1/solution.py` 观察完美通关的过程。

## 教师教学与成绩评估 (For Teachers)

平台为教师提供自动化评分支持。
- **成绩触发与保存**：每当学生前端点击“重置状态”按钮，或者学生的 Python WebSocket 脚本断开连接时，系统会自动抓取当前双物理引擎的存活 HP 状态。
- **成绩查询**：成绩将被追加记录到根目录的 `logs/session_results.jsonl` 文件中。
- **格式说明**：
  ```json
  {"timestamp": 1786701211.47, "session_id": "conn_1234_1786701190", "env_no_rules_final_hp": -5, "env_rules_final_hp": 100}
  ```
  教师可以编写简单的脚本读取该文件，比对 `env_rules_final_hp` 是否保持为 `100` 以判定学生编写的控制逻辑和本体规则是否成功起到了保护作用。

## 更多设计文档
- `SPEC.md`: 项目核心设计思想与哲学。
- `tech_spec.md`: 技术架构细节与 WebSocket 通信规范。
- `Level.md`: 关卡设计（当前支持 Level 1，规划了风力、视觉等高级关卡）。
- `level_solution.md`: 关卡难点解析与教学评分指引。