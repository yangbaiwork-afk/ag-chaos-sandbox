# Ag-Chaos Sandbox Technical Specification (tech_spec.md)

## 系统架构

本项目采用前后端分离的数字孪生架构。

- **后端 (FastAPI + MuJoCo)**:
  - 承载物理引擎和逻辑校验。
  - **Level 管理**: 不同的关卡代码存放在 `src/ag_chaos_sandbox/levels/` 下。
  - **双实例物理环境**: 每个 Level 在启动时，会初始化两个 MuJoCo 实例：
    - `env_no_rules`: 不加载/忽略拦截逻辑，动作指令无脑执行。
    - `env_rules`: 加载当前 Level 的拦截逻辑，校验动作合法性。
  - **WebSocket 总线**: 接收前端指令广播给两个环境；以高频度（约60Hz）将两个环境的骨骼、植物状态、系统日志打包发送给前端。

- **前端 (HTML + Three.js)**:
  - 负责 3D 渲染和用户交互。
  - 维护两套渲染场景（Scene_NoRules 和 Scene_Rules）。
  - **渲染模式**: 支持两分屏（左右并排渲染）或单屏独占（通过 UI 切换）。
  - UI 统一控制，按钮点击后，只发送一个动作信号，后端负责分发。

## 通用控制接口

所有前端发往后端的 WebSocket 消息为简单的字符串命令：
- `Target:{id}`: 瞄准指定 ID 的番茄。`Target:-1` 为归位。
- `Cut`: 挥舞机械臂剪切。
- `Spray`: 开启末端喷雾。

后端发往前端的 WebSocket 消息体结构：
```json
{
  "env_no_rules": {
    "arm_skeleton": [...],
    "plant_structure": {...},
    "tomato_hp": 100,
    "system_status": "...",
    "active_action": "...",
    "current_target_dist": 0.0
  },
  "env_rules": {
    "arm_skeleton": [...],
    "plant_structure": {...},
    "tomato_hp": 100,
    "system_status": "...",
    "active_action": "...",
    "current_target_dist": 0.0
  }
}
```

## 扩展新 Level 的流程
1. 在 `levels/` 下新建文件夹 `levelX`。
2. 编写 `generator.py`（负责生成特定的 MuJoCo XML 场景，例如增加风力节点、改变植物形态）。
3. 编写 `rules.json`（设定该 Level 的独有 Ontology 规则）。
4. 在主程序中引入新 Level 的控制器。
