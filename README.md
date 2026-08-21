# Himmel Hermes ☀️

> **A privacy-safe, reproducible downstream of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).**

**Himmel**은 공식 Hermes Agent를 직접 덮어쓰지 않고, 검증된 upstream 버전에 작은 downstream 변경을 더해 운영하기 위한 공개 배포판입니다. 공식 소스의 장점을 유지하면서 Telegram 운영, 승인 UI, 진행 상태, gateway 안정성처럼 실제 장기 운영에서 필요한 동작을 보강합니다.

이 저장소는 개인 Hermes 환경을 그대로 복사한 것이 아닙니다. **공식 upstream의 clean source에 공개 가능한 변경만 적용해 다시 만든 전체 소스 저장소**입니다.

## 무엇이 다른가요?

Himmel의 downstream 계층은 다음 동작을 추가하거나 강화합니다.

1. 포함 플랜 사용량을 넘기지 않도록 하는 fail-closed 보호
2. persona별 진행 상태와 제한된 heartbeat 표시
3. allowlist 기반 gateway restart broker와 systemd 처리
4. 현재 세션으로 한정된 reply context
5. Telegram rich-message 정책 통합
6. turn 종료 시 progress·media 정리
7. Telegram group-routing 제외 규칙
8. 구조화되고 지역화된 human-approval UI
9. Honcho identity 설정의 안전한 fresh-read 무효화

간단한 patch 범위는 [`.himmel/PATCHSET.md`](.himmel/PATCHSET.md), 정확한 upstream 기준은 [`.himmel/UPSTREAM.json`](.himmel/UPSTREAM.json)에서 확인할 수 있습니다.

## 설치

### 요구 사항

- Python `3.11`–`3.13`
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git

### Linux · macOS · WSL2

```bash
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv/bin/hermes
```

### Windows PowerShell

```powershell
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv\Scripts\hermes.exe
```

Provider credential은 설치 후 자신의 로컬 환경에서 설정하세요. `.env`, token, key 파일은 Git에 커밋하면 안 됩니다.

## 개인정보와 공개 범위

이 저장소에 **포함되지 않는 것**:

- 개인 profile·SOUL·memory·session·메시지 본문
- API key, credential, cookie, token, `.env`
- cron 실행 이력과 개인 automation state
- Kanban DB와 gateway runtime state
- 개인 홈 경로, Telegram 사용자 ID, Obsidian vault 경로
- 원본 비공개 patch 본문

공개 저장소에는 실행 가능한 source, 테스트, MIT 라이선스, upstream 식별 정보와 공개 가능한 downstream 코드만 포함합니다.

## 현재 상태

| 항목 | 값 |
|---|---|
| 채널 | **Public Preview** |
| Upstream tag | `v2026.8.18` |
| Upstream commit | `e624e9fde561e1add9388384012b295fde669ade` |
| Downstream focused tests | `230 passed` |
| Honcho regression | `25 passed × 3` |
| Full suite | `34,607 passed · 12 failed · 308 skipped` |

현재 preview에는 upstream 또는 플랫폼 환경에서 재현되는 알려진 테스트 실패가 남아 있습니다. 따라서 자동 운영 승격판이 아니라 **직접 검토해 설치하는 공개 preview**로 배포합니다. 릴리스 식별 정보는 [`HIMMEL_RELEASE.json`](HIMMEL_RELEASE.json)에 있습니다.

## Upstream과 라이선스

Himmel은 Nous Research의 공식 제품이나 공식 릴리스가 아닌 독립 downstream입니다.

- Upstream: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- 공식 문서: [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs)
- License: [MIT](LICENSE)
- Downstream notice: [HIMMEL_NOTICE.md](HIMMEL_NOTICE.md)

공식 Hermes 설치 스크립트는 upstream 버전을 설치합니다. **Himmel을 설치하려면 이 저장소를 clone하여 위의 source 설치 절차를 사용하세요.**
