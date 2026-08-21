"""Focused tests for the human-centered Telegram approval card."""

from plugins.platforms.telegram.approval_ui import (
    approval_decision_label,
    build_approval_prompt,
)


def _choices(prompt):
    return [choice for row in prompt.button_rows for _, choice in row]


def test_korean_prompt_puts_human_context_above_collapsed_command():
    prompt = build_approval_prompt(
        command="python3 apply.py --target config.yaml",
        description="overwrite project env/config file",
        purpose="새 표시 방식을 적용하기 위해 로컬 설정을 갱신해",
        approval_kind="terminal",
        allow_permanent=True,
        language="ko",
    )

    assert "실행 승인이 필요해" in prompt.text
    assert "새 표시 방식을 적용" in prompt.text
    assert "왜 승인이 필요한가?" in prompt.text
    assert '<blockquote expandable>' in prompt.text
    assert "python3 apply.py" in prompt.text
    assert prompt.text.index("새 표시 방식을 적용") < prompt.text.index("python3 apply.py")
    assert _choices(prompt)[:2] == ["once", "deny"]
    assert _choices(prompt)[2:] == ["session", "always"]
    assert prompt.rich_markdown.startswith("# 🛡️ 실행 승인이 필요해")
    assert "# 무엇을 하려는 작업인가?" in prompt.rich_markdown
    assert "# 왜 승인이 필요한가?" in prompt.rich_markdown
    assert "<details>\n<summary>기술 세부 정보</summary>" in prompt.rich_markdown
    assert "<blockquote" not in prompt.rich_markdown
    assert prompt.rich_markdown.index("<details>") < prompt.rich_markdown.index("python3 apply.py")
    assert prompt.rich_markdown.index("python3 apply.py") < prompt.rich_markdown.index("</details>")


def test_missing_purpose_is_honest_and_keeps_original_four_scopes_visible():
    prompt = build_approval_prompt(
        command="rm -rf build",
        description="recursive delete",
        purpose="",
        approval_kind="terminal",
        allow_permanent=True,
        language="ko",
    )

    assert "목적을 전달하지 않았어" in prompt.text
    assert "목적을 추측하지 않을게" in prompt.text
    assert _choices(prompt) == ["once", "deny", "session", "always"]


def test_execute_code_hides_permanent_scope_when_backend_disallows_it():
    prompt = build_approval_prompt(
        command="execute_code <<'PY'\nprint('x')\nPY",
        description="execute_code script execution",
        purpose="검사 결과를 계산해",
        approval_kind="execute_code",
        allow_permanent=False,
        language="ko",
    )

    assert "Python 코드는 파일을 바꾸거나" in prompt.text
    assert _choices(prompt) == ["once", "deny", "session"]


def test_dynamic_content_is_html_escaped_and_bounded():
    prompt = build_approval_prompt(
        command="<script>" + "x" * 5000,
        description="<unsafe>",
        purpose="<b>목적</b>",
        language="ko",
    )

    assert "<script>" not in prompt.text
    assert "&lt;script&gt;" in prompt.text
    assert "<unsafe>" not in prompt.text
    assert "&lt;unsafe&gt;" in prompt.text
    assert "<b>목적</b>" not in prompt.text
    assert "&lt;b&gt;목적&lt;/b&gt;" in prompt.text
    assert len(prompt.text) < 4096


def test_korean_decision_labels_are_human_readable():
    assert approval_decision_label("once", language="ko") == "✅ 이번만 승인했어"
    assert approval_decision_label("deny", language="ko") == "❌ 거부했어"
