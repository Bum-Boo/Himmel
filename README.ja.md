[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh-CN.md) | [Español](README.es.md) | [اردو](README.ur-pk.md)

# Himmel Hermes ☀️

> [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) を基にした、プライバシーに配慮した再現可能な独立 downstream ディストリビューションです。

Himmel は、特定された Hermes Agent upstream のクリーンなソースツリーに、小規模で公開された downstream レイヤーを適用します。Upstream agent を維持しながら、長期的な Telegram・gateway 運用で使われる quota 保護、進捗・承認表示、reply の範囲、後処理、再起動処理、routing 除外、Honcho identity の更新を強化します。

このリポジトリは、個人の Hermes 環境をコピーしたものではありません。特定された upstream baseline と公開 downstream 変更から再構築した、実行可能な完全なソースツリーです。個人 profile、credential、会話、runtime database、非公開のローカル provenance patch は含みません。

## Downstream の範囲

Himmel は次の動作を追加または強化します。

1. included-plan quota の fail-closed 保護
2. 範囲を限定した persona の進捗・status 表示
3. allowlist に基づく gateway restart broker と systemd 処理
4. 現在の session に限定した reply context
5. Telegram rich-message policy の統合
6. turn 単位の progress・media cleanup
7. 明示的な Telegram group-routing 除外
8. 構造化・ローカライズされた human-approval UI
9. fresh-read による Honcho identity cache の無効化

簡潔な範囲は [`.himmel/PATCHSET.md`](.himmel/PATCHSET.md)、正確な upstream 識別情報は [`.himmel/UPSTREAM.json`](.himmel/UPSTREAM.json) を参照してください。

## Source からのインストール

### 必要条件

- Python `3.11`–`3.13`（package 要件は `>=3.11,<3.14`）
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git

Linux、macOS、WSL2：

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

インストール後、provider credential はローカル環境で設定してください。`.env`、API key、token、cookie、credential file を commit しないでください。

Hermes 公式のインストール script は Himmel ではなく upstream ディストリビューションをインストールします。Himmel を実行するには、このリポジトリを clone して上記の source インストールを使用してください。Wheel と source distribution の build は、リポジトリの Nix build 経路以外では意図的に非対応です。`uv sync` による editable install は対応しています。

source tree には互換性とテストのため、upstream Windows installer の `scripts/install.ps1` が残されています。この script は upstream installer contract に従うもので、Himmel の推奨 install path ではありません。Himmel には上記の pinned source 手順を使ってください。

## はじめに

POSIX では `.venv/bin/hermes`、Windows では `.venv\Scripts\hermes.exe` を使って次のコマンドを実行します。

```text
hermes                 対話型 agent を開始
hermes --tui           モダンな terminal UI を開始
hermes setup           setup wizard を実行
hermes model           model と provider を設定
hermes tools           tool と toolset を設定
hermes gateway setup   messaging platform を設定
hermes gateway start   messaging gateway を開始
hermes doctor          インストールを診断
hermes --help           現在のコマンド一覧を表示
```

ユーザー設定は `~/.hermes/config.yaml`、secret は `~/.hermes/.env` に保存します。Upstream ドキュメントは [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/) にあります。一部は upstream のインストール・release 動作を説明しているため、Himmel にはこの README の source インストール手順を使用してください。

## Release status

| 項目 | 値 |
|---|---|
| Himmel version | `2026.08.1-preview.1` |
| Channel | **Public Preview** |
| Upstream tag | `v2026.8.18` |
| Upstream peeled commit | `e624e9fde561e1add9388384012b295fde669ade` |
| Python package metadata | `hermes-agent` `0.20.4` |
| Downstream focused tests | `230 passed` |
| Honcho regression | 3 つの新規 process でそれぞれ `25 passed` |
| Tooling tests | `64 passed` |
| Full suite | `34,607 passed, 12 failed, 308 skipped` |

Upstream または platform 環境に由来する既知の test failure が残っています。そのため、この release はインストール前に内容を確認する利用者向けの public preview であり、自動的な production 昇格版ではありません。Machine-readable な記録は [`HIMMEL_RELEASE.json`](HIMMEL_RELEASE.json) にあります。

## プライバシーと公開範囲

この公開リポジトリには次のものを含みません。

- 個人 profile、SOUL、memory、session、message 内容
- API key、credential、cookie、token、`.env`
- cron history と個人 automation state
- Kanban database と gateway runtime state
- 個人 home path、Telegram user ID、非公開 vault path
- 非公開の生 patch provenance

実行可能な source、test、維持された MIT license、upstream 識別記録、公開 downstream code を含みます。

## Upstream への謝辞と license

Himmel は独立した downstream ディストリビューションです。Nous Research の公式製品・release ではなく、Nous Research による承認を受けたものでもありません。

- Upstream project: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- Upstream ドキュメント: [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)
- Downstream notice: [HIMMEL_NOTICE.md](HIMMEL_NOTICE.md)
- License: [MIT](LICENSE)

法的な再利用・再配布には MIT license が適用され、[`LICENSE`](LICENSE) に記載された著作権・許諾表示の条件に従う必要があります。それとは別に、追加の license 条件ではなくお願いです。この downstream work を改変または共有する際は、[@Bum-Boo](https://github.com/Bum-Boo) と [Himmel の元リポジトリ](https://github.com/Bum-Boo/Himmel) に言及していただけると幸いです。
