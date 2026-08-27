[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh-CN.md) | [Español](README.es.md) | [اردو](README.ur-pk.md)

# Himmel Hermes ☀️

> [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)의 개인정보 보호형·재현 가능한 독립 downstream 배포판입니다.

Himmel은 식별 가능한 Hermes Agent upstream 기준의 깨끗한 전체 소스에 작고 공개된 downstream 계층을 적용합니다. Upstream agent를 유지하면서 장기 Telegram·gateway 운영에 쓰이는 할당량 보호, 진행·승인 표시, reply 범위, 정리, 재시작 처리, routing 제외, Honcho identity 갱신 동작을 보강합니다.

이 저장소는 개인 Hermes 환경을 복사한 것이 아닙니다. 식별된 upstream 기준과 공개 downstream 변경으로 재구성한 실행 가능한 전체 소스 트리이며, 개인 profile·credential·대화·runtime database·원본 로컬 provenance patch는 포함하지 않습니다.

## Downstream 범위

Himmel은 다음 동작을 추가하거나 강화합니다.

1. 포함 플랜 할당량을 위한 fail-closed 보호
2. 범위가 제한된 persona 진행 상태와 status 표시
3. allowlist 기반 gateway restart broker와 systemd 처리
4. 현재 session으로 제한된 reply context
5. Telegram rich-message 정책 통합
6. turn 단위 progress·media 정리
7. 명시적인 Telegram group-routing 제외
8. 구조화되고 지역화된 human-approval UI
9. fresh-read Honcho identity cache 무효화

간단한 범위는 [`.himmel/PATCHSET.md`](.himmel/PATCHSET.md), 정확한 upstream 식별 정보는 [`.himmel/UPSTREAM.json`](.himmel/UPSTREAM.json)에서 확인할 수 있습니다.

## Source 설치

### 요구 사항

- Python `3.11`–`3.13` (package 요구 범위: `>=3.11,<3.14`)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git

Linux, macOS, WSL2:

```bash
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv/bin/hermes
```

Windows PowerShell:

```powershell
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv\Scripts\hermes.exe
```

설치 후 provider credential은 로컬에서 설정하세요. `.env`, API key, token, cookie, credential 파일을 commit하지 마세요.

공식 Hermes 설치 script는 Himmel이 아니라 upstream 배포판을 설치합니다. Himmel을 실행하려면 이 저장소를 clone하고 위 source 설치 절차를 사용하세요. Wheel과 source distribution build는 저장소의 Nix build 경로 밖에서는 의도적으로 지원하지 않으며, `uv sync` editable 설치는 지원합니다.

source tree에는 호환성과 테스트를 위해 upstream Windows installer인 `scripts/install.ps1`가 남아 있습니다. 이 script는 upstream installer 계약을 따르며 Himmel의 권장 설치 경로가 아닙니다. Himmel은 위의 pinned source 절차로 설치하세요.

## 시작하기

POSIX에서는 `.venv/bin/hermes`, Windows에서는 `.venv\Scripts\hermes.exe`로 다음 명령을 실행합니다.

```text
hermes                 대화형 agent 시작
hermes --tui           최신 terminal UI 시작
hermes setup           설정 wizard 실행
hermes model           model과 provider 설정
hermes tools           tool과 toolset 설정
hermes gateway setup   messaging platform 설정
hermes gateway start   messaging gateway 시작
hermes doctor          설치 상태 진단
hermes --help           현재 command 도움말 표시
```

사용자 설정은 `~/.hermes/config.yaml`, secret은 `~/.hermes/.env`에 둡니다. Upstream 문서는 [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)에 있습니다. 일부 문서는 upstream 설치·release 동작을 설명하므로 Himmel 설치에는 이 README의 source 절차를 사용하세요.

## Release 상태

| 항목 | 값 |
|---|---|
| Himmel version | `2026.08.1-preview.1` |
| Channel | **Public Preview** |
| Upstream tag | `v2026.8.18` |
| Upstream peeled commit | `e624e9fde561e1add9388384012b295fde669ade` |
| Python package metadata | `hermes-agent` `0.20.4` |
| Downstream focused tests | `230 passed` |
| Honcho regression | 새 process 3개에서 각각 `25 passed` |
| Tooling tests | `64 passed` |
| Full suite | `34,607 passed, 12 failed, 308 skipped` |

Upstream 또는 platform 환경의 알려진 test failure가 남아 있습니다. 따라서 이 release는 설치 전 직접 검토하는 사용자를 위한 public preview이며 자동 production 승격판이 아닙니다. Machine-readable 기록은 [`HIMMEL_RELEASE.json`](HIMMEL_RELEASE.json)에 있습니다.

## 개인정보와 공개 범위

이 공개 저장소에는 다음 항목이 포함되지 않습니다.

- 개인 profile, SOUL, memory, session, message 내용
- API key, credential, cookie, token, `.env`
- cron history와 개인 automation state
- Kanban database와 gateway runtime state
- 개인 home 경로, Telegram user ID, 비공개 vault 경로
- 원본 비공개 patch provenance

실행 가능한 source, test, 유지된 MIT license, upstream 식별 기록, 공개 downstream code만 포함합니다.

## Upstream 감사와 license

Himmel은 독립 downstream 배포판이며 Nous Research의 공식 제품·release가 아니고 Nous Research의 보증을 받지 않습니다.

- Upstream project: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- Upstream 문서: [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)
- Downstream notice: [HIMMEL_NOTICE.md](HIMMEL_NOTICE.md)
- License: [MIT](LICENSE)

법적 재사용과 재배포에는 MIT license가 적용되며, [`LICENSE`](LICENSE)에 명시된 저작권·허가 고지 조건을 따라야 합니다. 이와 별개로 추가 license 조건이 아닌 예의상의 부탁입니다. 이 downstream 작업을 수정하거나 공유할 때 [@Bum-Boo](https://github.com/Bum-Boo)와 [Himmel 원본 저장소](https://github.com/Bum-Boo/Himmel)를 언급해 주세요.
