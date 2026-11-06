---
name: interview-voice
description: 在 DeepSeek Harness 使用麦克风转写和 Windows 本地朗读进行逐轮语音面试；处理开麦授权、模型准备与文字回退。
---

语音模式首次说明操作链路：Agent 朗读题目 → 用户点原生麦克风回答 → 停止录音 → 校对转写并点击发送 → Agent 评分/追问。Harness 不是常开全双工语音；不声称自动听到回答或自动发送。

原生语音设置：插件 → 语音输入（@deepseek-ai/dsh-experimental-voice-input-bundle）→ 启用。首次使用缺少资源时按界面“下载并准备”，这是用户手动下载，需要网络和磁盘。用户自行在系统/应用弹窗批准麦克风；拒绝时给出切换文字输入的选择，不反复弹窗。

选择语音模式视为允许朗读当前面试题，但不是允许后台录音或上传新服务。朗读：先用文件写工具把题目写到工作区 UTF-8 文本，再运行：

```text
powershell.exe -NoProfile -File <bundle>/scripts/speak.ps1 -TextFile <question.txt>
```

脚本仅调用 Windows System.Speech；使用系统已安装的中文声音，缺少时回报实际错误并提示在 Windows 语音设置安装中文语音包，期间继续文字提问。不能为绕过权限而换执行器。需要提升时通过 Harness 原生审批说明“仅朗读这一道面试题”。

若 Windows 提示“running scripts is disabled”，先请求用户当次批准，再对同一命令添加 `-ExecutionPolicy Bypass`，仅放行该子进程，不更改系统策略；拒绝时继续文字提问。脚本以 UTF-8 BOM 保存以兼容 Windows PowerShell 5.1。`-CheckOnly` 可验证中文声音，不播放音频。

只依据用户确认发送的文字评内容与组织结构。没有实际音频分析和时长时不评发音、音色、口音、情绪、停顿、语速。转写明显误识别关键术语，先让用户确认再扣知识分。语音错误/设备断开时保留本题与已有回答，提示一项可执行修复步骤，不重复创建会话。
