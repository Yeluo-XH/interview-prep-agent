# 实现与验证说明

## 数据流与职责

`cordis.patch.yml` 注册独立的 `interview-prep` 预设，组合 persona、文件工具、PowerShell、Skill、Web 与上下文压缩工具。五个 `SKILL.md` 定义每阶段的证据标准、输入输出和交互方式。技能说明由 Harness 按需加载。

JD/简历的语义分析、题目生成和回答内容判断由 Harness 配置的模型完成。`scripts/interview_store.py` 提供确定性的输入校验、加权计算、状态保存和知识卡检索接口。工作流由模型按预设指令执行，Python 存储器不独立编排模型调用。

| 部件 | 负责内容 | 验证方式 |
|---|---|---|
| Agent 预设与技能 | 阶段路由、证据约束、逐题教学/考试流程 | 当前安装的 Harness 实际挂载和五技能加载检查 |
| 存储 CLI | 阶段数据、需求引用、会话与作答记录 | 单元测试与 `scripts/demo.py` |
| 评分计算 | 五个 0–4 分维度转百分制 | 固定输入验证 78.75 分、拒绝无效值 |
| 知识检索 | 关键词匹配本地 JSON 知识卡 | 命中顺序与无匹配测试 |
| 语音 | Harness 原生转写流程、Windows System.Speech 朗读 | 本地中文声音可用性检查；麦克风与播放仍待端到端验收 |

## 状态与数据模型

每个会话独立保存为 `interview-data/<session-id>/state.json`：

```text
intake → jd → gaps → questions → mock → review
```

`pause` 将状态设为 paused；继续 `answer` 会转回 active。`finish` 将状态设为 finished，并生成本轮统计。这是面试数据进度管理，不是后台自动运行的任务引擎。

需求矩阵、差距与题库保存为带 `items` 的 JSON，需求使用 R ID，题目使用 Q ID。差距和题目中引用的需求必须存在。题库建立后改变 JD/差距应新建会话，已有作答时禁止替换题库。完整最小输入见 [examples](../examples)。

## 评分

`总分 = Σ(维度分 × 权重 / 4)`，权重：正确性 35、相关性 20、深度 20、证据 15、结构 10。每维须提供理由；输入需为有限的 0–4 数值，布尔值、NaN、越界值和空回答会被拒绝。

同一题的每次作答保存 attempt。总结仅计每题最新一次状态；跳过和未回答题不进入均分。模型评分的一致性和有效性尚未经过实际样本量化评估，不以测试通过替代模型效果验证。

## 文件写入

写入同目录临时文件并 fsync 后使用 `os.replace` 替换状态文件，减少写入中断导致 JSON 被截断的风险。排他创建 `.write.lock` 防止同一会话并发写入。进程异常退出可能留下锁文件；确认没有写入进程后才可手动清理。

会话 ID 限制字符与长度，检查目录链接不跳出数据根目录；这只覆盖工具的正常使用路径校验，不是完整的不可信并发文件系统隔离实现。系统权限由 Harness 管理。

## 可运行演示与测试边界

```powershell
python scripts/demo.py
python -m unittest discover -s tests -v
```

演示通过子进程调用真实 CLI，加载虚构 JD、差距、题库和预设人工评分，覆盖持久化、暂停、继续和总结。无参数时使用临时目录自动清理；`--output demo-output` 可保留状态。示例得分 78.75 是计算验证，不是一次真实模型评测。

GitHub Actions 在 Windows/Linux、Python 3.10/3.12 上运行上述命令；它不安装 Harness，不访问账户，不测试麦克风或联网模型。完整 Agent 验收需要另在 Harness 中使用实际材料测试。
