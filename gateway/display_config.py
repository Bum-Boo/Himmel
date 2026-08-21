"""Per-platform display/verbosity configuration resolver.

Provides ``resolve_display_setting()`` — the single entry-point for reading
display settings with platform-specific overrides and sensible defaults.

Resolution order (first non-None wins):
    1. ``display.platforms.<platform>.<key>``  — explicit per-platform user override
    2. ``display.<key>``                       — global user setting
    3. ``_PLATFORM_DEFAULTS[<platform>][<key>]``  — built-in sensible default
    4. ``_GLOBAL_DEFAULTS[<key>]``              — built-in global default

Exception: ``display.streaming`` is CLI-only.  Gateway streaming follows the
top-level ``streaming`` config unless ``display.platforms.<platform>.streaming``
sets an explicit per-platform override.

Backward compatibility: ``display.tool_progress_overrides`` is still read as a
fallback for ``tool_progress`` when no ``display.platforms`` entry exists.  A
config migration (version bump) automatically moves the old format into the new
``display.platforms`` structure.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Overrideable display settings and their global defaults
# ---------------------------------------------------------------------------
# These are the settings that can be configured per-platform.
# Other display settings (compact, personality, skin, etc.) are CLI-only
# and don't participate in per-platform resolution.

_GLOBAL_DEFAULTS: dict[str, Any] = {
    "tool_progress": "all",
    "tool_progress_grouping": "accumulate",  # "accumulate" = edit one bubble; "separate" = one msg per tool
    "show_reasoning": False,
    # How a reasoning/thinking summary is rendered when show_reasoning is on.
    #   "code"      -> 💭 **Reasoning:** + fenced code block (legacy default)
    #   "blockquote"-> each line prefixed with "> "
    #   "subtext"   -> each line prefixed with "-# " (Discord small grey subtext)
    # Discord defaults to "subtext"; everywhere else defaults to "code".
    "reasoning_style": "code",
    "tool_preview_length": 0,
    "streaming": None,  # None = follow top-level streaming config
    # Gateway-only assistant/status chatter controls. These default on for
    # back-compat, but mobile platforms can opt down to final-answer-first.
    "interim_assistant_messages": True,
    "long_running_notifications": True,
    "busy_ack_detail": True,
    # Whether busy_input_mode=steer sends a visible "Steered into current run"
    # acknowledgment after successfully injecting the user's mid-turn message.
    # Disable when the platform should steer silently (the text still lands in
    # the active run; only the confirmation echo is suppressed).
    "busy_steer_ack_enabled": True,
    "persona_progress_max_per_turn": 5,
    "persona_progress_single_message": True,
    "persona_progress_on_start": True,
    # Optional threshold-based replacement copy for long-running gateway
    # heartbeat bubbles. Default None preserves the legacy
    # "⏳ Working — N min" text exactly.
    "long_running_heartbeat_messages": None,
    "long_running_heartbeat_media": None,
    # Optional static in-character progress copy for tool_progress: persona.
    "persona_progress_messages": None,
    "persona_progress_selection": "sequential",
    "persona_progress_media": None,
    "persona_heartbeat_messages": None,
    # When true, delete tool-progress / "⏳ Working — N min" / status bubbles
    # after the final response lands on platforms that support message
    # deletion (e.g. Telegram). Off by default — progress is still shown
    # live, just cleaned up after success so the chat doesn't fill up with
    # stale breadcrumbs. Failed runs leave bubbles in place as breadcrumbs.
    "cleanup_progress": False,
    # Live working-state status on platforms whose typing indicator renders
    # text (Slack's assistant status line). Values:
    #   "full" / true  -> verb + argument preview ("is running pytest…")
    #   "verb"         -> verb only ("is running…") — keeps file paths and
    #                     commands out of shared channels
    #   "off" / false  -> static text (typing_status_text or "is thinking...")
    # Independent of tool_progress: works even when progress bubbles are off
    # (Slack's default), and costs no extra API calls — the existing typing
    # refresh cadence just renders different text.
    "live_status": "full",
}

# ---------------------------------------------------------------------------
# Sensible per-platform defaults — tiered by platform capability
# ---------------------------------------------------------------------------
# Tier 1 (high): Supports message editing, typically personal/team use
# Tier 2 (medium): Supports editing but often workspace/customer-facing
# Tier 3 (low): No edit support — each progress msg is permanent
# Tier 4 (minimal): Batch/non-interactive delivery

_TIER_HIGH = {
    "tool_progress": "all",
    "show_reasoning": False,
    "tool_preview_length": 40,
    "streaming": None,  # follow global
    "interim_assistant_messages": True,
    "long_running_notifications": True,
    "busy_ack_detail": True,
    "persona_progress_max_per_turn": 5,
    "persona_progress_single_message": True,
    "persona_progress_on_start": True,
}

_TIER_MEDIUM = {
    "tool_progress": "new",
    "show_reasoning": False,
    "tool_preview_length": 40,
    "streaming": None,
    "interim_assistant_messages": True,
    "long_running_notifications": True,
    "busy_ack_detail": True,
    "persona_progress_max_per_turn": 5,
    "persona_progress_single_message": True,
    "persona_progress_on_start": True,
}

_TIER_LOW = {
    "tool_progress": "off",
    "show_reasoning": False,
    "tool_preview_length": 40,
    "streaming": False,
    "interim_assistant_messages": False,
    "long_running_notifications": False,
    "busy_ack_detail": False,
    "persona_progress_max_per_turn": 5,
    "persona_progress_single_message": True,
    "persona_progress_on_start": True,
}

_TIER_MINIMAL = {
    "tool_progress": "off",
    "show_reasoning": False,
    "tool_preview_length": 0,
    "streaming": False,
    "interim_assistant_messages": False,
    "long_running_notifications": False,
    "busy_ack_detail": False,
    "persona_progress_max_per_turn": 5,
    "persona_progress_single_message": True,
    "persona_progress_on_start": True,
}

_PLATFORM_DEFAULTS: dict[str, dict[str, Any]] = {
    # Tier 1 — full edit support, personal/team use
    # Telegram is usually a mobile inbox: keep tool_progress quiet by default.
    # Profiles that want in-character progress can opt into
    # display.platforms.telegram.tool_progress: persona without leaking raw
    # tool names/paths/args.
    "telegram":    {
        **_TIER_HIGH,
        "tool_progress": "off",
        "busy_ack_detail": False,
    },
    # Discord has a native "subtext" primitive (-# small grey text) that reads
    # as metadata rather than content, so reasoning summaries default to it
    # here instead of the fenced code block used elsewhere.
    "discord":     {**_TIER_HIGH, "reasoning_style": "subtext"},

    # Tier 2 — edit support, often customer/workspace channels
    # Slack: tool_progress off by default — Bolt posts cannot be edited like CLI;
    # "new"/"all" spam permanent lines in channels (hermes-agent#14663).
    "slack":           {
        **_TIER_MEDIUM,
        "tool_progress": "off",
        "long_running_notifications": False,
        "busy_ack_detail": False,
    },
    "mattermost":      _TIER_MEDIUM,
    "matrix":          _TIER_MEDIUM,
    "feishu":          _TIER_MEDIUM,

    # Tier 3 — no edit support, progress messages are permanent
    "signal":          _TIER_LOW,
    "whatsapp":        _TIER_MEDIUM,  # Baileys bridge supports /edit
    # WhatsApp Cloud API: Meta added message editing in 2023 but the
    # Hermes Cloud adapter doesn't implement edit_message yet, so we
    # stay on TIER_LOW (tool_progress off) to avoid spamming each
    # status update as a separate message. Promote to TIER_MEDIUM once
    # Cloud's edit_message lands.
    "whatsapp_cloud":  _TIER_LOW,
    # Photon (managed iMessage over the gRPC sidecar) and BlueBubbles are both
    # permanent-message iMessage inboxes with no message-edit support, so both
    # stay TIER_LOW. This keeps tool progress, interim scratch commentary,
    # "still working" heartbeats, and busy-ack iteration detail out of the
    # user's iMessage thread. Without this entry Photon inherited the noisy
    # global ("all") defaults and compacted/narrated on nearly every turn.
    "photon":          _TIER_LOW,
    "bluebubbles":     _TIER_LOW,
    "weixin":          _TIER_LOW,
    "wecom":           _TIER_LOW,
    "wecom_callback":  _TIER_LOW,
    "dingtalk":        _TIER_LOW,

    # Tier 4 — batch or non-interactive delivery
    "email":           _TIER_MINIMAL,
    "sms":             _TIER_MINIMAL,
    "webhook":         _TIER_MINIMAL,
    "homeassistant":   _TIER_MINIMAL,
    "api_server":      {**_TIER_HIGH, "tool_preview_length": 0},
}

# Canonical set of per-platform overrideable keys (for validation).
OVERRIDEABLE_KEYS = frozenset(_GLOBAL_DEFAULTS.keys())


def resolve_display_setting(
    user_config: dict,
    platform_key: str,
    setting: str,
    fallback: Any = None,
) -> Any:
    """Resolve a display setting with per-platform override support.

    Parameters
    ----------
    user_config : dict
        The full parsed config.yaml dict.
    platform_key : str
        Platform config key (e.g. ``"telegram"``, ``"slack"``).  Use
        ``_platform_config_key(source.platform)`` from gateway/run.py.
    setting : str
        Display setting name (e.g. ``"tool_progress"``, ``"show_reasoning"``).
    fallback : Any
        Fallback value when the setting isn't found anywhere.

    Returns
    -------
    The resolved value, or *fallback* if nothing is configured.
    """
    display_cfg = user_config.get("display") or {}

    # 1. Explicit per-platform override (display.platforms.<platform>.<key>)
    platforms = display_cfg.get("platforms") or {}
    plat_overrides = platforms.get(platform_key)
    if isinstance(plat_overrides, dict):
        val = plat_overrides.get(setting)
        if val is not None:
            return _normalise(setting, val)

    # 1b. Backward compat: display.tool_progress_overrides.<platform>
    if setting == "tool_progress":
        legacy = display_cfg.get("tool_progress_overrides")
        if isinstance(legacy, dict):
            val = legacy.get(platform_key)
            if val is not None:
                return _normalise(setting, val)

    # 2. Global user setting (display.<key>).  Skip display.streaming because
    # that key controls only CLI terminal streaming; gateway token streaming is
    # governed by the top-level streaming config plus per-platform overrides.
    if setting != "streaming":
        val = display_cfg.get(setting)
        if val is not None:
            return _normalise(setting, val)

    # 3. Built-in platform default
    plat_defaults = _PLATFORM_DEFAULTS.get(platform_key)
    if plat_defaults:
        val = plat_defaults.get(setting)
        if val is not None:
            return val

    # 4. Built-in global default
    val = _GLOBAL_DEFAULTS.get(setting)
    if val is not None:
        return val

    return fallback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(setting: str, value: Any) -> Any:
    """Normalise YAML quirks (bare ``off`` → False in YAML 1.1)."""
    if setting == "tool_progress":
        if value is False:
            return "off"
        if value is True:
            return "all"
        val = str(value).strip().lower()
        if val in {"false", "0", "no"}:
            return "off"
        if val in {"true", "1", "yes", "on"}:
            return "all"
        return val if val in {"off", "new", "all", "verbose", "log", "persona"} else "all"
    if setting in {
        "show_reasoning",
        "streaming",
        "interim_assistant_messages",
        "long_running_notifications",
        "busy_ack_detail",
        "busy_steer_ack_enabled",
        "thinking_progress",
        "persona_progress_single_message",
        "persona_progress_on_start",
    }:
        if isinstance(value, str):
            val = value.strip().lower()
            if val == "generic" and setting == "long_running_notifications":
                return "generic"
            return val in {"true", "1", "yes", "on", "raw", "verbose"}
        return bool(value)
    if setting == "cleanup_progress":
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "on"}
        return bool(value)
    if setting == "live_status":
        # Tri-state: "full" (verb + preview), "verb" (verb only), "off".
        if value is True:
            return "full"
        if value is False:
            return "off"
        val = str(value).strip().lower()
        if val in {"true", "1", "yes", "on", "all"}:
            return "full"
        if val in {"false", "0", "no"}:
            return "off"
        return val if val in {"full", "verb", "off"} else "full"
    if setting == "tool_progress_grouping":
        val = str(value).lower()
        return val if val in ("accumulate", "separate") else "accumulate"
    if setting == "reasoning_style":
        val = str(value).lower()
        return val if val in ("code", "blockquote", "subtext") else "code"
    if setting == "tool_preview_length":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if setting == "persona_progress_max_per_turn":
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 1
    return value


_DEFAULT_PERSONA_PROGRESS_MESSAGES = [
    "확인하는 중이야.",
    "단서를 확인하는 중이야.",
    "조용히 맞춰보는 중이야.",
    "마법식이 어긋나지 않게 보고 있어.",
    "조금만 기다려. 흐름을 맞추는 중이야.",
]


def build_long_running_heartbeat_text(
    user_config: dict,
    platform_key: str,
    *,
    elapsed_minutes: int,
    status_detail: str = "",
) -> str:
    """Return gateway long-running heartbeat copy.

    Default preserves the upstream deterministic text. Profiles can opt into
    static threshold-based copy with display.platforms.<platform>.
    long_running_heartbeat_messages. No LLM is called and status details are
    appended only when the selected rule explicitly asks for it.
    """
    try:
        elapsed = max(0, int(elapsed_minutes))
    except (TypeError, ValueError):
        elapsed = 0
    detail = str(status_detail or "")
    default_text = f"⏳ Working — {elapsed} min{detail}"

    rules = resolve_display_setting(
        user_config,
        platform_key,
        "long_running_heartbeat_messages",
        None,
    )
    if not isinstance(rules, list):
        return default_text

    selected: dict[str, Any] | None = None
    selected_threshold = -1
    for raw_rule in rules:
        if not isinstance(raw_rule, dict):
            continue
        try:
            threshold = int(raw_rule.get("threshold_minutes", 0))
        except (TypeError, ValueError):
            continue
        text = str(raw_rule.get("text") or "").strip()
        if text and threshold <= elapsed and threshold >= selected_threshold:
            selected = raw_rule
            selected_threshold = threshold

    if selected is None:
        return default_text

    text = str(selected.get("text") or "").strip()
    if "{elapsed_minutes}" in text or "{minutes}" in text:
        try:
            text = text.format(elapsed_minutes=elapsed, minutes=elapsed)
        except (KeyError, IndexError, ValueError):
            pass
    if selected.get("append_status_detail") is True and detail:
        text = f"{text}{detail}"
    return text


def build_persona_progress_message(
    user_config: dict,
    platform_key: str,
    *,
    sequence: int = 0,
    tool_name: str | None = None,
    rng=None,
) -> str:
    """Return a safe persona progress line for gateway tool progress.

    tool_progress: persona intentionally ignores tool names, arguments, paths,
    and previews in rendered text. tool_name is accepted only for caller
    compatibility and future local selection rules.
    """
    messages = resolve_display_setting(
        user_config,
        platform_key,
        "persona_progress_messages",
        None,
    )
    if not isinstance(messages, list) or not messages:
        messages = _DEFAULT_PERSONA_PROGRESS_MESSAGES
    cleaned = [str(m).strip() for m in messages if str(m).strip()]
    if not cleaned:
        cleaned = _DEFAULT_PERSONA_PROGRESS_MESSAGES

    selection = str(
        resolve_display_setting(
            user_config,
            platform_key,
            "persona_progress_selection",
            "sequential",
        )
        or "sequential"
    ).lower()
    if selection == "random":
        if rng is None:
            import random
            rng = random
        try:
            return str(rng.choice(cleaned))
        except Exception:
            return cleaned[0]
    try:
        idx = max(0, int(sequence)) % len(cleaned)
    except (TypeError, ValueError):
        idx = 0
    return cleaned[idx]


def _resolve_progress_media(
    user_config: dict,
    platform_key: str,
    message: str,
    setting: str,
) -> dict[str, str] | None:
    """Resolve a deterministic media rule for a rendered progress line."""
    text = str(message or "").strip()
    if not text:
        return None
    rules = resolve_display_setting(user_config, platform_key, setting, None)
    if not isinstance(rules, list):
        return None
    for raw_rule in rules:
        if not isinstance(raw_rule, dict):
            continue
        path = (
            raw_rule.get("path")
            or raw_rule.get("media_path")
            or raw_rule.get("image_path")
        )
        if not isinstance(path, str) or not path.strip():
            continue
        exact = (
            raw_rule.get("text")
            or raw_rule.get("message")
            or raw_rule.get("exact")
        )
        contains = raw_rule.get("contains")
        matched = False
        if isinstance(exact, str) and exact.strip():
            matched = text == exact.strip()
        if not matched and isinstance(contains, str) and contains.strip():
            matched = contains.strip() in text
        if not matched:
            continue
        media: dict[str, str] = {"path": path.strip()}
        caption = raw_rule.get("caption")
        if isinstance(caption, str) and caption.strip():
            media["caption"] = caption.strip()
        return media
    return None


def resolve_persona_progress_media(
    user_config: dict,
    platform_key: str,
    message: str,
) -> dict[str, str] | None:
    return _resolve_progress_media(
        user_config, platform_key, message, "persona_progress_media"
    )


def resolve_long_running_heartbeat_media(
    user_config: dict,
    platform_key: str,
    message: str,
) -> dict[str, str] | None:
    return _resolve_progress_media(
        user_config, platform_key, message, "long_running_heartbeat_media"
    )
