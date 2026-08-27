[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh-CN.md) | [Español](README.es.md) | [اردو](README.ur-pk.md)

# Himmel Hermes ☀️

> [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的注重隐私、可复现的独立下游发行版。

Himmel 在一个已明确标识的、干净的 Hermes Agent 上游源码树上应用小型且公开的下游层。它保留上游 agent，同时增强长期 Telegram 和 gateway 运行所需的配额保护、进度与审批显示、reply 范围、清理、重启处理、routing 排除和 Honcho identity 刷新行为。

本仓库并非个人 Hermes 环境的副本，而是由已标识的上游基线和公开下游更改重建的完整可运行源码树。个人 profile、credential、对话、runtime database 以及原始本地 provenance patch 均不包含在内。

## 下游范围

Himmel 添加或增强以下行为：

1. included-plan 配额的 fail-closed 保护；
2. 有限范围的 persona 进度和 status 显示；
3. 基于 allowlist 的 gateway restart broker 与 systemd 处理；
4. 仅限当前 session 的 reply context；
5. Telegram rich-message policy 集成；
6. turn 级 progress 和 media 清理；
7. 明确的 Telegram group-routing 排除规则；
8. 结构化、本地化的 human-approval UI；
9. fresh-read Honcho identity cache 失效处理。

简要范围见 [`.himmel/PATCHSET.md`](.himmel/PATCHSET.md)，精确的上游标识见 [`.himmel/UPSTREAM.json`](.himmel/UPSTREAM.json)。

## 从源码安装

### 要求

- Python `3.11`–`3.13`（package 要求为 `>=3.11,<3.14`）
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git

Linux、macOS 或 WSL2：

```bash
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv/bin/hermes
```

Windows PowerShell：

```powershell
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv\Scripts\hermes.exe
```

安装后，请在本地环境中配置 provider credential。不要提交 `.env`、API key、token、cookie 或 credential 文件。

Hermes 官方安装脚本安装的是上游发行版，而不是 Himmel。要运行 Himmel，请 clone 本仓库并使用上述源码安装方式。除仓库的 Nix build 路径外，wheel 和 source distribution build 被有意设为不支持；`uv sync` editable 安装受支持。

source tree 为兼容性与测试保留了 upstream Windows installer：`scripts/install.ps1`。该脚本遵循 upstream installer contract，并不是 Himmel 的推荐安装路径。安装 Himmel 时请使用上面的 pinned source 流程。

## 快速开始

在 POSIX 系统中通过 `.venv/bin/hermes`、在 Windows 中通过 `.venv\Scripts\hermes.exe` 运行以下命令：

```text
hermes                 启动交互式 agent
hermes --tui           启动现代 terminal UI
hermes setup           运行设置向导
hermes model           配置 model 和 provider
hermes tools           配置 tool 和 toolset
hermes gateway setup   配置 messaging platform
hermes gateway start   启动 messaging gateway
hermes doctor          诊断安装状态
hermes --help           显示当前命令参考
```

用户设置存放在 `~/.hermes/config.yaml`，secret 存放在 `~/.hermes/.env`。上游文档位于 [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)。部分文档描述上游安装和 release 行为，因此安装 Himmel 时请使用本 README 的源码步骤。

## Release 状态

| 项目 | 值 |
|---|---|
| Himmel version | `2026.08.1-preview.1` |
| Channel | **Public Preview** |
| Upstream tag | `v2026.8.18` |
| Upstream peeled commit | `e624e9fde561e1add9388384012b295fde669ade` |
| Python package metadata | `hermes-agent` `0.20.4` |
| Downstream focused tests | `230 passed` |
| Honcho regression | 在 3 个全新 process 中各 `25 passed` |
| Tooling tests | `64 passed` |
| Full suite | `34,607 passed, 12 failed, 308 skipped` |

目前仍有来自上游或 platform 环境的已知 test failure。因此，本 release 是供用户安装前自行审查的 public preview，而不是自动提升为 production 的版本。机器可读记录见 [`HIMMEL_RELEASE.json`](HIMMEL_RELEASE.json)。

## 隐私与公开边界

本公开仓库不包含：

- 个人 profile、SOUL、memory、session 和 message 内容；
- API key、credential、cookie、token 和 `.env`；
- cron history 和个人 automation state；
- Kanban database 和 gateway runtime state；
- 个人 home path、Telegram user ID 和私有 vault path；
- 原始私有 patch provenance。

仓库包含可运行 source、test、保留的 MIT license、上游标识记录和公开下游 code。

## 上游致谢与 license

Himmel 是独立的下游发行版，并非 Nous Research 的官方产品或 release，也未得到 Nous Research 的认可。

- 上游项目：[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- 上游文档：[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)
- 下游声明：[HIMMEL_NOTICE.md](HIMMEL_NOTICE.md)
- License：[MIT](LICENSE)

法律上的再使用和再分发受 MIT license 约束，并须遵守 [`LICENSE`](LICENSE) 中的版权与许可声明条件。除此之外，作为礼貌请求而非额外 license 条件，在改编或分享此下游工作时，敬请提及 [@Bum-Boo](https://github.com/Bum-Boo) 和 [Himmel 原始仓库](https://github.com/Bum-Boo/Himmel)。
