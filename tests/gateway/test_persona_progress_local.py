from queue import Queue
from types import SimpleNamespace

from gateway.display_config import (
    build_long_running_heartbeat_text,
    resolve_display_setting,
    resolve_long_running_heartbeat_media,
    resolve_persona_progress_media,
)
from gateway.run import TurnRunner
from gateway.turn_context import TurnContext


def _context(config):
    return TurnContext(
        source=SimpleNamespace(chat_id="1", platform="telegram"),
        platform_key="telegram",
        _run_still_current=lambda: True,
        progress_mode="persona",
        tool_progress_enabled=True,
        progress_queue=Queue(),
        user_config=config,
        resolve_display_setting=resolve_display_setting,
    )


def test_persona_callback_never_queues_raw_tool_details():
    config = {
        "display": {
            "platforms": {
                "telegram": {
                    "tool_progress": "persona",
                    "persona_progress_messages": ["확인하는 중이야."],
                    "persona_progress_max_per_turn": 1,
                    "persona_progress_single_message": True,
                }
            }
        }
    }
    ctx = _context(config)
    runner = TurnRunner(SimpleNamespace(), ctx)

    runner.progress_callback(
        "tool.started",
        "terminal",
        "cat /var/lib/hermes-fixture/secret.txt",
        {"command": "cat /var/lib/hermes-fixture/secret.txt", "token": "never-render"},
    )

    queued = ctx.progress_queue.get_nowait()
    assert queued == ("__replace__", "확인하는 중이야.")
    assert "terminal" not in repr(queued)
    assert "/var/lib/hermes-fixture/secret.txt" not in repr(queued)
    assert "never-render" not in repr(queued)

    runner.progress_callback("tool.started", "read_file", "/tmp/private", {})
    assert ctx.progress_queue.empty()


def test_persona_callback_queues_resolved_media_without_tool_details():
    config = {
        "display": {
            "platforms": {
                "telegram": {
                    "tool_progress": "persona",
                    "persona_progress_messages": ["호오.."],
                    "persona_progress_media": [
                        {"text": "호오..", "path": "/tmp/reaction.jpg"}
                    ],
                }
            }
        }
    }
    ctx = _context(config)
    TurnRunner(SimpleNamespace(), ctx).progress_callback(
        "tool.started", "web_search", "private query", {"query": "private query"}
    )

    queued = ctx.progress_queue.get_nowait()
    assert queued == (
        "__progress_media__",
        "호오..",
        {"path": "/tmp/reaction.jpg"},
        True,
    )
    assert "web_search" not in repr(queued)
    assert "private query" not in repr(queued)


def test_heartbeat_rules_hide_status_detail_unless_explicitly_enabled():
    config = {
        "display": {
            "platforms": {
                "telegram": {
                    "long_running_heartbeat_messages": [
                        {"threshold_minutes": 1, "text": "조금 더 보고 있어."}
                    ],
                    "long_running_heartbeat_media": [
                        {"text": "조금 더 보고 있어.", "path": "/tmp/wait.jpg"}
                    ],
                }
            }
        }
    }
    text = build_long_running_heartbeat_text(
        config,
        "telegram",
        elapsed_minutes=5,
        status_detail=" — terminal /srv/hermes-lab-fixture/private",
    )
    assert text == "조금 더 보고 있어."
    assert "terminal" not in text
    assert resolve_long_running_heartbeat_media(config, "telegram", text) == {
        "path": "/tmp/wait.jpg"
    }
    assert resolve_persona_progress_media(config, "telegram", "unmatched") is None
