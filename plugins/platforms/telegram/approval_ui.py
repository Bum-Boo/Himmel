"""Human-centered Telegram approval prompt rendering.

This module only formats display text and button labels. Security decisions,
redaction, authorization, and approval resolution stay in their existing
owners (tools.approval, gateway.run, and TelegramAdapter).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Mapping


_STRINGS = {
    "en": {
        "header": "🛡️ <b>Action approval required</b>",
        "not_run": "<i>Nothing has run yet.</i>",
        "purpose": "What this is for",
        "missing_purpose": (
            "The profile did not provide a plain-language purpose. "
            "The command was not used to guess one."
        ),
        "why": "Why approval is required",
        "reason_terminal": (
            "Hermes security rules classified this command as requiring "
            "explicit user review because it may affect files, settings, "
            "services, or other system state."
        ),
        "reason_execute_code": (
            "This Python script can change files or start other commands, so "
            "Hermes requires explicit approval before it runs."
        ),
        "details": "Technical details",
        "detector": "Security finding",
        "command": "Command or code",
        "hint": "Choose below. Denying keeps the operation blocked.",
        "smart_deny": "Smart DENY: an owner override applies to this one operation only.",
        "once": "✅ Allow Once",
        "deny": "❌ Deny",
        "session": "✅ Session",
        "always": "✅ Always",
        "result_once": "✅ Approved once",
        "result_session": "🕒 Approved for this session",
        "result_always": "⚠️ Approved permanently",
        "result_deny": "❌ Denied",
        "resolved_by": "{label} — {user}",
    },
    "ko": {
        "header": "🛡️ <b>실행 승인이 필요해</b>",
        "not_run": "<i>아직 아무 작업도 실행되지 않았어.</i>",
        "purpose": "무엇을 하려는 작업인가?",
        "missing_purpose": (
            "프로필이 사람용 작업 목적을 전달하지 않았어. "
            "명령어만 보고 목적을 추측하지 않을게."
        ),
        "why": "왜 승인이 필요한가?",
        "reason_terminal": (
            "파일·설정·서비스 또는 시스템 상태에 영향을 줄 수 있어 "
            "Hermes 보안 규칙이 사용자 확인이 필요한 작업으로 분류했어."
        ),
        "reason_execute_code": (
            "이 Python 코드는 파일을 바꾸거나 다른 명령을 실행할 수 있어서 "
            "실행 전에 명시적인 승인이 필요해."
        ),
        "details": "기술 세부 정보",
        "detector": "보안 탐지 이유",
        "command": "실행할 명령 또는 코드",
        "hint": "아래에서 선택해줘. 거부하면 작업은 실행되지 않아.",
        "smart_deny": "Smart DENY: 소유자 재승인은 이번 한 작업에만 적용돼.",
        "once": "✅ 이번만 승인",
        "deny": "❌ 거부",
        "session": "🕒 이 대화에서 허용",
        "always": "⚠️ 항상 허용",
        "result_once": "✅ 이번만 승인했어",
        "result_session": "🕒 이 대화에서 허용했어",
        "result_always": "⚠️ 항상 허용했어",
        "result_deny": "❌ 거부했어",
        "resolved_by": "{label} — {user}",
    },
}


@dataclass(frozen=True)
class ApprovalPrompt:
    text: str
    rich_markdown: str
    button_rows: tuple[tuple[tuple[str, str], ...], ...]


def normalize_approval_language(value: str | None) -> str:
    """Return the supported approval UI language code."""
    raw = (value or "").strip().lower()
    return "ko" if raw == "ko" or raw.startswith("ko-") or raw in {"korean", "한국어"} else "en"


def _s(language: str, key: str) -> str:
    lang = normalize_approval_language(language)
    return _STRINGS[lang][key]


def _clip(value: str | None, limit: int) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _plain_static(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def _escape_rich_markdown(value: str) -> str:
    """Escape dynamic text without destroying the card's static rich markup."""
    escaped = html.escape(value, quote=False)
    return re.sub(r"([\\`*_\[\]#|])", r"\\\1", escaped)


def _code_fence(value: str) -> str:
    """Wrap arbitrary command text in a fence it cannot terminate."""
    runs = [len(match.group(0)) for match in re.finditer(r"`+", value)]
    fence = "`" * max(3, (max(runs) + 1) if runs else 3)
    return f"{fence}text\n{value}\n{fence}"


def build_approval_prompt(
    *,
    command: str,
    description: str,
    purpose: str | None,
    approval_kind: str = "terminal",
    allow_permanent: bool = True,
    allow_session: bool = True,
    smart_denied: bool = False,
    language: str = "en",
) -> ApprovalPrompt:
    """Build HTML text and semantic button rows for a Telegram approval card.

    Dynamic values are HTML-escaped here. The command is already redacted by
    the approval layer, but rendering still escapes it and applies a strict
    length cap so the final Bot API message stays below Telegram's limit.
    """
    purpose_text = _clip(purpose, 700)
    description_text = _clip(description, 700) or "security review required"
    command_text = _clip(command, 2200) or "(empty)"
    reason_key = "reason_execute_code" if approval_kind == "execute_code" else "reason_terminal"

    visible_purpose = purpose_text or _s(language, "missing_purpose")
    smart_notice_html = (
        f"\n\n<b>{_s(language, 'smart_deny')}</b>" if smart_denied else ""
    )
    smart_notice_rich = (
        f"\n\n**{_s(language, 'smart_deny')}**" if smart_denied else ""
    )
    text = (
        f"{_s(language, 'header')}\n"
        f"{_s(language, 'not_run')}\n\n"
        f"<b>{_s(language, 'purpose')}</b>\n"
        f"{html.escape(visible_purpose)}\n\n"
        f"<b>{_s(language, 'why')}</b>\n"
        f"{_s(language, reason_key)}\n\n"
        f"<blockquote expandable><b>{_s(language, 'details')}</b>\n"
        f"{_s(language, 'detector')}: {html.escape(description_text)}\n\n"
        f"{_s(language, 'command')}:\n"
        f"<code>{html.escape(command_text)}</code></blockquote>"
        f"{smart_notice_html}\n\n"
        f"<i>{_s(language, 'hint')}</i>"
    )
    rich_markdown = (
        f"# {_plain_static(_s(language, 'header'))}\n\n"
        f"*{_plain_static(_s(language, 'not_run'))}*\n\n"
        f"# {_s(language, 'purpose')}\n\n"
        f"{_escape_rich_markdown(visible_purpose)}\n\n"
        f"# {_s(language, 'why')}\n\n"
        f"{_s(language, reason_key)}\n\n"
        f"<details>\n<summary>{_s(language, 'details')}</summary>\n\n"
        f"**{_s(language, 'detector')}**\n\n"
        f"{_escape_rich_markdown(description_text)}\n\n"
        f"**{_s(language, 'command')}**\n\n"
        f"{_code_fence(command_text)}\n"
        f"</details>"
        f"{smart_notice_rich}\n\n"
        f"*{_s(language, 'hint')}*"
    )

    if normalize_approval_language(language) == "ko":
        rows: list[tuple[tuple[str, str], ...]] = [
            ((_s(language, "once"), "once"), (_s(language, "deny"), "deny")),
        ]
        if not smart_denied and allow_session:
            scope_row: list[tuple[str, str]] = [
                (_s(language, "session"), "session"),
            ]
            if allow_permanent:
                scope_row.append((_s(language, "always"), "always"))
            rows.append(tuple(scope_row))
    else:
        buttons: list[tuple[str, str]] = [(_s(language, "once"), "once")]
        if not smart_denied and allow_session:
            buttons.append((_s(language, "session"), "session"))
            if allow_permanent:
                buttons.append((_s(language, "always"), "always"))
        buttons.append((_s(language, "deny"), "deny"))
        rows = [tuple(buttons[i:i + 2]) for i in range(0, len(buttons), 2)]

    return ApprovalPrompt(
        text=text,
        rich_markdown=rich_markdown,
        button_rows=tuple(rows),
    )


def approval_decision_label(choice: str, *, language: str = "en") -> str:
    key = {
        "once": "result_once",
        "session": "result_session",
        "always": "result_always",
        "deny": "result_deny",
    }.get(choice, "result_deny")
    return _s(language, key)


def approval_resolved_text(choice: str, user: str, *, language: str = "en") -> str:
    label = approval_decision_label(choice, language=language)
    return _s(language, "resolved_by").format(label=label, user=user)


__all__ = [
    "ApprovalPrompt",
    "approval_decision_label",
    "approval_resolved_text",
    "build_approval_prompt",
    "normalize_approval_language",
]
