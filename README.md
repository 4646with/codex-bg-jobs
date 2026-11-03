# codex-bg-jobs

让 [Codex CLI](https://github.com/openai/codex) 像 Claude Code 一样**把长命令挂到后台跑，跑完自动接着干**。

装上插件后，你正常说“跑一下构建 / 跑完整测试 / 部署一下”，Codex 会：

1. 把命令放到后台启动，立刻告诉你 job id 和日志位置，然后结束这一轮，不再傻等；
2. 命令跑完后，插件自动给**当前会话**发一条 `[bg-job done]` 消息；
3. Codex 被这条消息唤醒，读日志、判断成功还是失败，然后继续之前的任务。

```
你：帮我跑一下构建：npm run build
Codex：已后台启动，Job ID：build-20261102-055411-76，跑完会自动通知我。
        …… 40 秒后 ……
[bg-job done] id=build-20261102-055411-76 status=exited 0 elapsed=40s
Codex：构建成功，退出码 0。接下来……
```

## 一句话安装

复制下面这句话，发给能操作本机终端的 agent：

```text
请按 https://github.com/4646with/codex-bg-jobs 的 README，检查本机兼容性并安装 bg-jobs 插件，核对并启用它的 SessionStart hook；如果需要我在 /hooks 中手动信任，请告诉我选哪一项，最后用后台任务运行 sleep 20 && echo done，验证原 Codex 会话能收到完成通知并读到 done。
```

## 手动安装

需要 Codex CLI **0.163 或更高版本**，并且在 macOS 或 Linux 上使用（依赖 `bash`、`perl`、`python3`，系统一般自带）。

**第 1 步：添加插件市场并安装**

```bash
codex plugin marketplace add 4646with/codex-bg-jobs
codex plugin add bg-jobs@codex-bg-jobs
```

**第 2 步：信任插件的 hook（只需一次）**

Codex 出于安全考虑，新安装插件里的 hook 默认不运行。打开 Codex，输入：

```
/hooks
```

找到 `bg-jobs` 的 `SessionStart` hook，选择信任（trust）。

> 不做这一步也能用，只是 Codex 不会**自动**使用后台模式，你需要在对话里说“用 background-jobs skill 跑……”。

**第 3 步：验证**

新开一个 Codex 会话，说：

```
请用后台任务运行 sleep 20 && echo done，完成后告诉我输出。
```

看到 Codex 回复 Job ID 并结束这一轮，约 20 秒后自己出现 `[bg-job done]` 并接着回复，就说明装好了。

## 原理

Codex 本身没有“后台命令 + 完成通知”机制，这个插件用 Codex 自带的几样东西拼出来：

| 组件 | 作用 |
|---|---|
| `SessionStart` hook | 每次会话开始时，往会话里注入一段规则：“超过约 30 秒的命令用后台跑”，并告诉 Codex 脚本的真实路径。所以**不需要**改 `AGENTS.md`。 |
| `background-jobs` skill | 详细用法说明：什么时候用、不要 `sleep` 轮询、收到完成通知后怎么做。 |
| `scripts/bg` 脚本 | 真正干活：后台启动命令、记录日志和退出码、结束时发通知。 |
| `CODEX_THREAD_ID` | Codex 执行命令时自带的环境变量，脚本靠它知道该通知哪个会话。 |
| `codex queue` | Codex 自带命令，给指定会话发消息。会话收到后会像收到你的新消息一样开始新的一轮。 |

一个关键细节：Codex 每条命令结束后会清理它启动的所有子进程，普通的 `nohup` / `&` 挡不住。脚本用 `setsid` 让后台进程脱离 Codex 的进程组，并且等它确认脱离成功后才返回，所以任务不会被中途杀掉，Codex 退出了任务也照样跑完。

## 手动使用 `bg`

脚本在插件安装目录里（会话开始时 hook 会告诉 Codex 具体路径），你也可以自己用：

```bash
BG=~/.codex/plugins/cache/codex-bg-jobs/bg-jobs/<版本>/skills/background-jobs/scripts/bg

$BG run -n build -- 'npm run build && npm test'   # 一个字符串：交给 bash -c，可用管道、&&
$BG run -n upload -- rsync -av dist/ host:/srv/   # 多个参数：原样执行
$BG run -n dev --no-notify -- 'npm run dev'       # 常驻进程，不需要完成通知

$BG list            # 最近 20 个任务
$BG status ID       # 状态：running / exited N / killed
$BG tail ID 80      # 日志最后 80 行
$BG wait ID 120     # 在本轮内最多等 120 秒（上限 600）
$BG kill ID         # 终止任务及其子进程
```

任务数据存放在 `~/.codex/bg-jobs/<id>/`：

| 文件 | 内容 |
|---|---|
| `cmd` | 执行的命令 |
| `log` | 标准输出 + 标准错误 |
| `exit` | 退出码（任务结束后才有） |
| `notify.log` | 发送完成通知的结果 |

设置环境变量 `CODEX_BG_ROOT` 可以改存放位置。

## 常见问题

**Codex 没有自动用后台模式？**
大概率是第 2 步没做，hook 没被信任。在 Codex 里运行 `/hooks` 检查。

**任务跑完了，但会话没有被唤醒？**
先看 `~/.codex/bg-jobs/<id>/notify.log`：
- 有 `Queued message ...`：通知已经发出。只有开着的 Codex 窗口才能被唤醒，确认任务结束时那个窗口还开着。窗口关了也不要紧，用 `bg status <id>` 就能看到结果。
- 文件不存在或有报错：确认后台进程环境里能找到 `codex` 命令。

**用 `codex exec`（非交互）运行时会被唤醒吗？**
不会。`exec` 跑完一轮就退出，没有开着的会话可以接收消息。任务和通知照常进行，结果可以用 `bg status` 查看。

**Windows 能用吗？**
暂不支持，脚本依赖 bash 和 POSIX 的 `setsid`。WSL 里应该可以用，但没有测试过。

## 卸载

```bash
codex plugin remove bg-jobs@codex-bg-jobs
codex plugin marketplace remove codex-bg-jobs
rm -rf ~/.codex/bg-jobs     # 可选：删除任务日志
```

## 许可证

MIT
