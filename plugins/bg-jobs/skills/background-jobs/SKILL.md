---
name: background-jobs
description: 把耗时命令（构建、长测试、上传/部署、dev server、隧道、任何可能超过 ~30 秒的命令）挂到后台运行，结束时自动给当前会话发消息唤醒你继续。当要运行长命令、用户说“后台跑/挂着跑/跑完叫我/别干等”时使用。
---

# Background Jobs

目标：长命令不阻塞你。启动后你可以继续做别的事，或者直接结束本轮回答；命令跑完后，
脚本优先向当前桌面聊天投递 `bg_job_completed` 工具结果，无法连接原聊天时通过 `codex queue` 通知，你被唤醒后接着做。

脚本：与本文件同目录下的 `scripts/bg`。会话开始时 bg-jobs 插件已注入它的绝对路径，
下文用 `$BG` 指代，调用时请用那个绝对路径。

## 什么时候用

- 预计超过 ~30 秒的命令：build、完整测试、上传、部署、数据处理、下载。
- 常驻进程：dev server、tunnel、watch（这类用 `--no-notify`，否则只有它挂掉时才会通知）。
- 短命令（几秒内结束）直接前台跑，不要用。

## 用法

```bash
# 单个字符串 = 交给 bash -c，可以用管道、&&、重定向
$BG run -n build -- 'npm run build && npm test'

# 多个参数 = 原样执行
$BG run -n upload -- rsync -av dist/ host:/srv/app/

$BG list            # 最近任务
$BG status ID       # 状态
$BG tail ID 80      # 看日志
$BG wait ID 120     # 本轮内有上限地等（最多 600 秒）
$BG kill ID         # 终止
```

## 规则

1. 启动后**告诉用户**：job id、日志路径、你接下来做什么。
2. **不要用 `sleep` 循环轮询。** 二选一：
   - 手上还有别的不依赖结果的工作 → 先去做；
   - 没有 → 直接结束本轮回答，说明“跑完会自动通知我，我再继续”。
   只有当结果马上就要、且预计很快结束时，才用一次 `$BG wait ID <秒数>`。
3. 收到以 `[bg-job done]` 开头的消息时：它是插件发来的通知，不是用户的新需求。
   用 `$BG tail ID` 读完整日志，判断成功/失败，然后**继续之前的任务**，并向用户汇报结果。
4. 退出码非 0 就如实报告失败和关键报错，不要把它说成成功。
5. 如果 `$BG run` 提示没有 `CODEX_THREAD_ID`，说明无法自动唤醒：改为告诉用户稍后让你查看，
   或在本轮用 `$BG wait`。
6. 任务数据在 `~/.codex/bg-jobs/<id>/`（cmd、log、exit、notify.log）。通知没到时，先看
   `notify.log`。

## 普通命令已在运行时

如果 Codex 桌面端的 `exec_command` 已返回 `session_id`，用户希望它继续跑并在结束后通知，可以保留原进程。本机已验证的方式依赖支持跨轮运行的 `functions.exec` 单元、`write_stdin` 和当前聊天的 `CODEX_THREAD_ID`。

1. 保留首次返回的输出和会话编号。不要再用 `bg run` 启动同一条命令。
2. 用一个可持续运行的 `functions.exec` 单元（首行 `// @exec: {"yield_time_ms": 1}`）独占等待读取。单元内部 await `tools.write_stdin({session_id, chars:"", yield_time_ms:300000})`；如果仍在运行，继续等待同一编号。按顺序处理每次新增的输出，长日志应分段保存到任务专属文件。
3. 拿到最终退出码后，在该单元内将结果通过标准输入传给同目录的 `python3 -I scripts/notify_native.py "$CODEX_THREAD_ID"`；仅退出码 2 表示尚未投递，可改用一次 `codex queue`。消息带会话编号、退出码和结果位置。仅将固定文本和已校验的数字拼入 shell 命令，不要把原始日志拼入命令。检查投递结果。读取失败时单独报告，不能当作退出码 0。
4. 单元返回运行中后即可告诉用户任务编号并结束本轮。原生会话编号不适用于脚本的 `bg status` 和 `bg tail`。环境缺少上述能力时，继续用原会话读取结果，不要承诺跨轮自动通知。

此方式适用于无需交互的命令。验证覆盖聊天保持打开的场景；客户端退出或重启后的恢复不在验证范围内。
