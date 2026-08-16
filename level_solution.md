# Ag-Chaos Sandbox Solutions & Scoring (level_solution.md)

## 评分机制设计

在教学中，学生可以通过观察对照组（无规则）和实验组（有规则）的不同表现，来学习如何编写合理的 `ontology.json` 规则。

每个 Level 设定的总分为 100 分。

### Level 1 解决方案标准
- **无规则对照组表现**: 学生会看到，如果随便点击喷洒和剪切，大概率会因为物理距离过近触发碰撞无敌帧机制，导致 HP 锐减至 0。
- **正确方向**:
  - `Cut` 动作：必须计算机械臂剪刀长度，设置 `min_safe_dist` (如 0.10m)，防止剪切操作时末端戳入果实体积内；同时设置 `max_effective_dist` (如 0.15m)，防止空气剪。
  - `Spray` 动作：必须设置 `min_effective_dist` (如 0.15m) 防止高压水柱破坏表皮；设置 `max_effective_dist` (如 0.30m) 防止水雾消散。
- **评分要点**:
  - 成功拦截危险近距离剪切 (+20分)
  - 成功拦截无效远距离喷洒 (+20分)
  - 在有效区间内完成动作并成功增加 HP (+60分)

### Level 2 (风力) 解决方案方向
- 必须引入外部环境变量（Wind Speed）。
- 在 `rules.json` 中添加条件表达式，如果 `Wind > threshold`，必须禁用所有雾化操作。

### Level 3 (视觉置信度) 解决方案方向
- 动作决策不能仅仅基于“存在目标”。
- 必须联合判断 `confidence_score` 和 `distance_to_critical_organs`。

### Level 4 (生理极限) 解决方案方向
- 必须具备计算 VPD (Vapor Pressure Deficit) 的能力。
- 从单纯的物理动作拦截，升级为对“灌溉”等生理影响动作的拦截。

## 数据记录与持久化 (Logging & Scoring Architecture)

为了支持教学评分，系统在后端实现自动日志记录功能：
- **触发条件**：当 WebSocket 断开连接（用户关闭页面/脚本结束）或用户主动点击 `Reset` 按钮时。
- **存储位置**：`logs/session_results.jsonl`
- **存储内容**：每一次 Session 的最终对照组 (无规则) 与 实验组 (有规则) 的剩余 HP，以及耗时记录。教师可以通过解析该 JSONL 文件对全班同学的最终表现进行打分。
