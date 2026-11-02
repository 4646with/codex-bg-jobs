#!/usr/bin/env bash
# SessionStart hook：把“长命令放后台跑”的规则和 bg 脚本的真实路径注入当前会话。
# 不依赖任何全局规则文件（AGENTS.md），装上插件即生效。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BG="$(cd "$HERE/.." && pwd)/skills/background-jobs/scripts/bg"
chmod +x "$BG" 2>/dev/null || true

read -r -d '' CTX <<EOF
[bg-jobs 插件] 本会话已启用后台任务能力。
- 预计超过约 30 秒的命令（build、完整测试、上传/部署、下载、数据处理），以及 dev server / tunnel / watch 这类常驻进程，一律用后台方式启动，不要前台阻塞等待：
    $BG run -n <名字> -- '<shell 命令>'
  常驻进程加 --no-notify。详细用法见 background-jobs skill。
- 启动后告诉用户 job id 和日志路径；手上有不依赖结果的工作就先做，没有就直接结束本轮，并说明“跑完会自动通知我”。不要用 sleep 循环轮询。
- 收到以 “[bg-job done]” 开头的消息：这是插件发来的完成通知，不是用户新需求。用 \`$BG tail <id>\` 读日志，如实报告成功/失败，然后继续之前的任务。
- 几秒内就能结束的短命令照常前台执行。
EOF

python3 -I -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":sys.argv[1]}}, ensure_ascii=False))' "$CTX"
