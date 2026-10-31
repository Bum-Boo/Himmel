# Himmel 테스트 스위트 정리 보고서 (2026-10-31, 클라우드 세션)

대상: `main`(d8aaa8e) 기준. 이전 세션 브랜치 `claude/himmel-test-suite-main-pjqjek`(8 커밋)을
이어받아 `claude/himmel-test-suite-finish-rhiec3`에서 마무리했다. 아래는 두 세션 커밋 전체를 다룬다.

분류: **검증된 결함**(재현 후 수정) / **정적 위험**(재현했지만 코드 수정은 소유자 판단) /
**이미 커버됨** / **비이슈**.

## 1. 요약

- CI `main` 실패 원인이던 `tests/gateway/test_session_api.py`는 **테스트 측 경쟁 조건**이며, 결정적으로
  재현한 뒤 수정했다(§3.1).
- 이 VM(루트 실행, IPv6 없음, DNS 없음, SQLite 3.45.1, 최소화 Ubuntu)에서 전체 스위트를 돌려
  CI에서는 가려져 있던 **비밀폐(non-hermetic) 테스트 19개 파일 / 30개 실패**를 찾았고, 그중 FTS 2건을 뺀
  전부를 수정했다. 남은 2건은 실제 제품 결함(SQLite 3.45.x 한정)으로 판단해 테스트를 약화하지 않고 남겼다(§4.1).
- `check-attribution`은 매핑 파일을 추가하지 않았다. 필요한 파일은 §5.
- PR #6은 이번 수정 후 테스트는 통과하지만 `check-attribution`은 그대로 실패한다(§6).

## 2. 실행한 명령과 결과

환경 준비(CI와 동일 extras):

```
uv sync --locked --python 3.11 --extra all --extra dev --extra anthropic --extra mistral \
  --extra fal --extra modal --extra daytona --extra hindsight --extra parallel-web
```

- `.venv`: 시스템 Python 3.11.18 + SQLite **3.45.1**(WAL-reset 버그 버전 → journal_mode=DELETE)
- `venv-managed`(스크래치): uv 관리 Python 3.11.15 + SQLite **3.53.1** — CI(uv 관리 3.11.14)와 같은 계열

| 명령 | 이전(인계 시점 브랜치 tip `bcea054`) | 이후(본 브랜치) |
|---|---|---|
| `scripts/run_tests.sh` (시스템 venv) | 3056 파일, 34556 통과 / **30 실패** / 350 스킵 | __SYSTEM_AFTER__ |
| `scripts/run_tests.sh` (관리형 venv, CI 동등) | (미실행; CI `main` 런 33090138425: slice 5에서 1 실패) | __MANAGED_AFTER__ |
| `scripts/run_tests.sh tests/gateway/test_session_api.py` (main, 3회) | 20/20 통과 ×3 (경쟁 조건이라 이 VM에선 우연히 통과) | 20/20 통과 ×3 |
| 위 테스트를 수정 전 본문 + 지연 주입으로 실행 | **1 실패** (CI와 동일 `TypeError: cannot unpack non-iterable NoneType`) | 통과 |
| `ruff check .` | All checks passed | All checks passed |
| `python scripts/check-windows-footguns.py --all` | 없음(985 파일) | 없음 |
| `ty check` + `scripts/lint_diff.py` (main 대비, 권고용) | — | __TY_DIFF__ |
| PR #6을 본 브랜치에 로컬 병합 후 `tests/hermes_cli/test_restart_broker.py tests/gateway/test_session_api.py` | — | 40/40 통과 |

JS 레인: __JS__

## 3. 변경 사항

### 3.1 `test_session_api.py` 실패 (검증된 결함 — 테스트 경쟁 조건)

- 경로: `gateway/platforms/api_server.py:4056`에서 에이전트 실행을 백그라운드 태스크로 띄우고 SSE 헤더를
  먼저 보낸다. 태스크는 `:3964`에서 히스토리를 await한 다음에야 `_run_agent`를 부른다. 클라이언트가 끊기거나
  핸들러가 취소되면 `:4085-4095` → `:4112`가 실행을 취소한다(의도된 동작).
- 기존 테스트는 본문을 읽지 않고 클라이언트를 닫았다 → 느린 러너에서는 `_run_agent` 호출 전에 취소되어
  `mock_run.call_args`가 `None`. 제품 코드는 정상이다.
- 이전 세션(95a47ff): 본문을 끝까지 읽고 `run.completed`와 1회 호출을 단언. 같은 파일의 다른 스트림
  테스트는 이미 본문을 읽고 있어 형제 경로 누락은 없음.
- 이번 세션(45ef473): `_conversation_history_for_session`에 0.2초 지연을 주입해 경쟁을 결정적으로 만들었다
  (`tests/gateway/test_session_api.py:447-457`). 이 지연 아래에서 수정 전 본문은 CI와 같은 오류로 실패하고,
  수정 후 본문은 3회 연속 통과했다.
  테스트를 약화한 것이 아니라 경쟁 창을 고정한 것.

### 3.2 이전 세션 커밋 검증

| 커밋 | 내용 | 검증 방법 | 분류 |
|---|---|---|---|
| 95a47ff | SSE 본문 드레인 | §3.1 결정적 재현 | 검증된 결함(테스트) |
| 8c720f1 | teams 모듈 import 시 실제 lazy-install(PyPI) 방지 | 전체 스위트 통과, 회귀 테스트 존재 | 검증된 결함(테스트) |
| 9b35454 | 시스템 유닛 생성 시 대상 HOME 플러그인 import·디렉터리 생성 방지 (`hermes_cli/gateway.py`, `gateway/config.py`) | 제품 파일만 main으로 되돌리면 회귀 테스트 2개 실패, 복원 시 통과 | 검증된 결함 |
| 72e8a37, 6834e1a | 브라우저 테스트가 실제 HERMES_HOME/npm 설치에 닿지 않게 | 전체 스위트 통과 | 검증된 결함(테스트) |
| a41452e | IPv6 스택 없는 호스트에서 디버그 포트 탐색이 항상 점유 포트 반환 (`hermes_cli/browser_connect.py:236`) | 되돌리면 기존 테스트 포함 2개 실패(이 VM은 IPv6 없음) | 검증된 결함 |
| ec8b7ed | FTS 검색 투영 테스트가 풀링된 리더를 추적 | 전체 스위트(양 venv) 통과 | 검증된 결함(테스트) |
| bcea054 | `HOME=/root` 같은 1단계 홈에서 `>> /root/.ssh/authorized_keys` 승인 우회 (`tools/approval.py:1229`) | 되돌리면 신규 4개 + 기존 `test_redirect_to_sensitive_target` 실패(루트 호스트) | 검증된 결함(보안) |

추가로 3d0223b: 8c720f1의 스텁 대입이 `ty` 권고 diff에 새 `invalid-assignment`를 만들어서 `patch.object`와 실제
시그니처로 바꿨다.

### 3.3 이번 세션에서 고친 비밀폐 테스트 (모두 `main`에서도 같은 VM에서 실패 재현)

| 커밋 | 파일 | 원인 | 조치 |
|---|---|---|---|
| e65abf4 (+973c965, 622adce, 75c4e04) | `tests/conftest.py:912` 외 slack/telegram/vision/web_extract 테스트 | `is_safe_url()`이 호스트를 실제 DNS로 조회하고, 프록시가 없으면 실패 시 차단(`tools/url_safety.py:448-473`). `run_tests.sh`는 프록시 변수를 지우므로 CI도 실제 DNS에 의존 중 | 지정 호스트만 가짜 공인 IP로 해석하는 opt-in 픽스처 `fake_public_dns` 추가. SSRF 가드는 그대로 실행되며, 사설 IP 응답은 여전히 차단됨을 별도 테스트로 확인 |
| 1677fe5, f4e99e4 | vision 텍스트 전용 가드, xAI 라벨, Meta 전환 | models.dev를 실제로 내려받음(`agent/image_routing.py:442`, `hermes_cli/providers.py:531`). 오프라인이면 "알 수 없음" → 설계상 폴백 | 합성 카탈로그 주입 + 대조 테스트(이미지 지원 카탈로그면 메인 유지) |
| 9cb7b47 | `test_goal_verdict_send.py`, `gateway/test_loop_command.py` | 이벤트 루프 스레드에서 goals DB 콜드 캐시는 0.25초만 기다리고 `None`으로 강등(`hermes_cli/goals.py:674,753`). 이 VM은 스키마 init이 약 1초 → `GoalManager.set()`이 조용히 저장 안 함 | 동기 픽스처(루프 밖)에서 DB를 미리 열고 성공 단언 |
| 2b6fc37 | `test_update_yes_flag.py` | `cmd_update` 재시작 단계가 실제 `find_gateway_pids`(`hermes_cli/update_cmd.py:6165`) 호출 → 병렬 실행 중 다른 테스트 프로세스를 발견 → conftest 가드가 `os.kill` 차단 → exit 1 (부하 시에만 실패) | `test_cmd_update.py`와 같은 디스커버리 패치. 다른 `cmd_update` 테스트 파일은 스파이로 확인한 결과 디스커버리에 닿지 않음 |
| a1de659 | `test_webhook_adapter.py` | IPv6 스택 없음 | v4 바인드와 connect 성공은 단언하고 v6 단언만 스킵 |
| 47b81e2 | `test_gateway_service.py` | `$USER=root`면 시스템 유닛 생성 거부(`hermes_cli/gateway.py:2695`, 의도된 동작) | 합성 서비스 계정으로 고정 |
| 768db0d, ea86318 | `test_migrate_xai.py`, `test_lazy_deps_durable_target.py` | 루트는 chmod 권한을 무시 | 기존 `test_doctor_journal_modes.py:145` 패턴대로 루트일 때 스킵(Windows 안전한 `getattr(os, "geteuid")`) |
| d5a981f | `test_state_db_malformed_repair.py` | SQLite 3.45는 `row N missing from index X`로 보고 | 두 문구 모두 허용(`hermes_cli/kanban_db.py:2028`과 동일). 복구 로직은 문구에 의존하지 않음 |
| 9b04465 | `test_ssh_environment.py` | `ssh` 바이너리 없음(연결은 이미 목) | PATH 확인만 스텁 |
| b992a79 | `test_execution_flag_detection.py` | 최소화 이미지의 `/usr/bin/man`은 안내만 출력하고 exit 0 | `man -w ls`가 실제 페이지 경로를 줄 때만 실행 |

## 4. 수정하지 않은 발견

### 4.1 SQLite 3.45.x에서 오래된(stale) FTS 인덱스가 재오픈 시 자가 복구되지 않음 — 검증된 결함(환경 한정)

- 재현: 손상된 FTS5 shadow 데이터에서 `DROP TABLE messages_fts`가 SQLite 3.45.1은
  `vtable constructor failed`, 3.53.1은 성공.
- 영향: 재오픈 복구(`hermes_state_schema.py:385`의 DROP → `:447` 로그)가 매번 실패 → FTS가 계속 분리된 채
  검색은 LIKE로 동작. 정본 메시지는 유지된다. `hermes doctor`가 감지하고(`hermes_cli/doctor.py:1741`)
  `hermes doctor --fix`(`drop_fts_rebuild`, 백업 포함)로 복구됨을 확인했다.
- 해당 환경: 시스템 SQLite 3.45.x에 링크된 Python(Ubuntu 24.04 시스템 Python 등). CI의 관리형 Python은 해당 없음.
- 테스트 `tests/state/test_fts_runtime_rebuild.py`의 2건은 이 결함을 정확히 드러내므로 약화하지 않았다.
- 제안: 재오픈 경로에서 `vtable constructor failed`일 때 기존 오프라인 복구(`repair_state_db_schema`, 잠금·백업
  포함)를 한 번 호출하거나, 최소한 오류 로그에 `hermes doctor --fix` 안내를 넣는 것. 살아있는 연결 중
  `writable_schema` 수술이 필요하므로 소유자 판단 사항으로 남김.

### 4.2 goals DB 부트스트랩 강등 — 정적 위험

- `hermes_cli/goals.py:674`의 0.25초 대기는 감시견 크래시 루프를 막기 위한 의도된 설계다. 그러나 스키마
  init이 느린 디스크/SQLite(위 3.45.1 + DELETE 저널)에서는 게이트웨이 시작 직후 첫 `/goal` 설정이
  저장되지 않을 수 있다(응답은 "설정됨"). 테스트만 고쳤고 제품 동작은 바꾸지 않았다.

### 4.3 테스트가 models.dev·DNS에 실제로 접속 — 정적 위험

- CI는 위 테스트들에서 실제 DNS·models.dev에 접속하고 있었다. 수정한 파일 외에도 남아 있을 수 있다.
  DNS가 없는 이 VM에서 전체 스위트를 통과시킨 것으로 DNS 의존은 대부분 제거됐다고 본다.
  models.dev는 디스크 캐시/백오프가 있어 오프라인에서 조용히 다른 경로를 탈 수 있으므로 완전히 확인하지 못했다.

## 5. `check-attribution` (매핑 미추가)

- 워크플로: `.github/workflows/contributor-check.yml:55` — 커밋 작성자 이메일마다 `contributors/emails/<이메일>`
  파일이 있어야 한다. push 이벤트(main)는 새 커밋 범위가 비어 통과하고, PR에서 실패한다.
- PR #6 커밋 3개의 작성자: `bumboo500y@gmail.com` → 매핑 없음.
- 소유자가 추가할 파일(내용 = GitHub 로그인 한 줄):

```
contributors/emails/bumboo500y@gmail.com
Bum-Boo
```

  생성 명령: `python3 scripts/add_contributor.py bumboo500y@gmail.com Bum-Boo`
- `main`의 초기 커밋 작성자 `Bum-Boo@users.noreply.github.com`은 `+`가 없어 자동 통과 대상이 아니다.
  이후 이 이메일로 PR을 올리면 `contributors/emails/Bum-Boo@users.noreply.github.com`도 필요하다.
- 이 브랜치의 커밋(작성자 `noreply@anthropic.com`)은 `*anthropic.com*` 예외로 통과한다.

## 6. PR #6(restart broker cooldown) 통과 여부

- CI 런 38434297026의 실패 2건: `check-attribution`, slice 5 `test_session_api.py`(main과 같은 실패).
- 본 브랜치에 PR #6을 로컬 병합하면 `test_restart_broker.py` + `test_session_api.py` 40/40 통과, 충돌 없음.
- 따라서 본 브랜치가 main에 들어간 뒤 PR #6을 갱신하면 **테스트는 통과, `check-attribution`은 §5 파일
  추가 전까지 계속 실패**한다.

## 7. 이 VM에서 검증하지 못한 것

- Windows/macOS 레인(`tests-os.yml`), Windows 전용·macOS 전용 마커 테스트
- 데스크톱(Electron) E2E, GUI, 실기기, Docker 이미지 빌드
- 실제 외부 서비스(Slack, Telegram, xAI, Meta, models.dev 등) — 모두 목/합성 데이터
- IPv6가 있는 호스트에서의 v6 단언(웹훅 테스트는 이 VM에서 스킵)
- 비루트 사용자로의 전체 실행(루트 전용 스킵 2건은 CI에서 실행됨)

## 8. 소유자 다음 단계

1. 이 브랜치를 PR로 열어 CI 확인(특히 slice 5, lint diff).
2. `contributors/emails/bumboo500y@gmail.com`(내용 `Bum-Boo`) 추가 여부 결정 → PR #6 재실행.
3. §4.1 FTS 자가 복구 개선 여부 결정(최소한 로그에 `hermes doctor --fix` 안내).
4. 테스트에서 models.dev 실접속을 막는 공통 픽스처(고정 카탈로그) 도입 검토.
