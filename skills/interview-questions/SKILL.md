---
name: interview-questions
description: 根据 JD 与简历差距生成分层面试题库，执行逐题模拟，对真实回答按统一标准评分并给出优化话术。
---

题库默认 12 题，可按用户题数调整；覆盖核心职责、短板、项目深挖、情景取舍、行为题。每题有 Q ID、requirement_ids、主题、难度、问题、考查点、followups、评分锚点、reference_answer。没确认的简历内容以假设问题询问，不预设用户做过。技术题按实际版本和岗位职级设定难度。

题库 JSON 用 {"items":[...]} 保存（interview_store.py set --stage questions）。初次进入模拟只展示题目概览；reference_answer 和评分要点只保存在本地，不在用户答题前展开。用户明确要求学习参考答案时可展示。

先确定教学/考试模式、文字/语音，默认 5 题。每次仅一道主问题；回答后最多一个针对性追问，追问归属同一 Q ID，不计作新的独立题。用户“跳过”记 skipped，不当错误扣分；“结束/暂停”先保存进度，只有“结束”才出本轮总结。教学模式即时反馈，考试模式延迟到结束。

评分先判断回答类型，按五个维度 0–4 给分：correctness(35%)、relevance(20%)、depth(20%)、evidence(15%)、structure(10%)。0=错误/无相关内容，1=片段且关键缺失，2=基本正确但解释不足，3=准确且能说明机制/案例，4=准确完整、边界清楚且能解释取舍。evidence 对知识题指推理/例子，对经历题指个人行动/真实结果，不强求虚构数字。短题的正确简答也能拿高分。

不能仅凭文字长度评分。每个维度附上回答引文、得分原因；明确事实性错误、遗漏点、表达问题。用本 Bundle scripts/interview_store.py answer 从评估 JSON 计算总分，禁止凭印象另算。输入：

```json
{"question_id":"Q01","answer":"用户原始回答","status":"answered","scores":{"correctness":3,"relevance":3,"depth":2,"evidence":2,"structure":3},"rationale":{"correctness":"引文与原因","relevance":"引文与原因","depth":"引文与原因","evidence":"引文与原因","structure":"引文与原因"},"improvements":["具体缺口"],"optimized_answer":"仅据已确认事实改写","followup":"一个追问"}
```

保存命令：python <bundle>/scripts/interview_store.py --root <data> answer --session <id> --file <evaluation.json>。用户改答同题会保留 attempt 历史。总结用 finish，统计每题最新已评分回答，跳过题不进入均分；空答题不产生分数。

反馈依次给：总分与分项、做得好的证据、最多三个主要不足、60–120 秒可口述的改写、一个追问。改写不得补造经历，缺口用【待补充】或给出明确的假设示例。结束生成 feedback.md：覆盖主题、均分、未覆盖题、错误清单、优先复习项、下一轮建议；不预测面试通过率。
