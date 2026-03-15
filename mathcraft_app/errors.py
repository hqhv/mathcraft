import re


def is_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    class_module = exc.__class__.__module__.lower()
    error_type = ""
    error_code = ""
    error_msg = ""
    if isinstance(body, dict):
        error_obj = body.get("error")
        if isinstance(error_obj, dict):
            error_type = str(error_obj.get("type", "")).lower()
            error_code = str(error_obj.get("code", "")).lower()
            error_msg = str(error_obj.get("message", "")).lower()

    if status_code == 401:
        return True

    explicit_auth_codes = {
        "invalid_api_key",
        "incorrect_api_key",
        "organization_forbidden",
        "permission_denied",
        "insufficient_permissions",
    }
    if (
        "authentication" in error_type
        or "permission" in error_type
        or error_code in explicit_auth_codes
    ):
        return True

    # Do not treat unrelated HTTP failures as auth unless we have explicit signals.
    if status_code is not None and status_code not in (401, 403):
        return False

    # For status-less errors, only trust message heuristics for likely provider exceptions.
    has_structured_provider_error = bool(error_type or error_code or error_msg)
    is_likely_provider_error = (
        "openai" in class_module or has_structured_provider_error or status_code is not None
    )
    if status_code is None and not is_likely_provider_error:
        return False

    msg = f"{str(exc).lower()} {error_type} {error_code} {error_msg}".strip()
    base_signals = [
        "invalid_api_key",
        "incorrect api key",
        "incorrect_api_key",
        "401 unauthorized",
        "organization_forbidden",
    ]
    if any(signal in msg for signal in base_signals):
        return True

    # Permission-oriented text fallback is only trusted for explicit 403 responses.
    if status_code == 403:
        permission_signals = [
            "permission denied",
            "insufficient permissions",
            "not authorized",
            "forbidden",
        ]
        return any(signal in msg for signal in permission_signals)

    return False


def classify_auth_error(exc: Exception) -> tuple[str, str]:
    status_code = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    error_code = ""
    error_msg = ""
    if isinstance(body, dict):
        error_obj = body.get("error")
        if isinstance(error_obj, dict):
            error_code = str(error_obj.get("code", "")).lower()
            error_msg = str(error_obj.get("message", "")).lower()

    combined = f"{str(exc).lower()} {error_msg}".strip()
    invalid_key_codes = {"invalid_api_key", "incorrect_api_key"}
    invalid_key_signals = [
        "invalid_api_key",
        "incorrect api key",
        "incorrect_api_key",
        "api key is invalid",
        "bad api key",
    ]
    if status_code == 401 or error_code in invalid_key_codes or any(
        signal in combined for signal in invalid_key_signals
    ):
        return "invalid_key", "API key appears invalid or expired. Please check it again."

    return (
        "authorization",
        "Authentication/authorization failed. Please verify your API key and organization or project permissions.",
    )


def auth_error_user_message(exc: Exception) -> str:
    return classify_auth_error(exc)[1]


def auth_error_reason(exc: Exception) -> str:
    return classify_auth_error(exc)[0]


def is_context_length_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    combined = str(exc).lower()

    if isinstance(body, dict):
        error_obj = body.get("error")
        if isinstance(error_obj, dict):
            error_type = str(error_obj.get("type", "")).lower()
            error_code = str(error_obj.get("code", "")).lower()
            error_msg = str(error_obj.get("message", "")).lower()
            combined = f"{combined} {error_type} {error_code} {error_msg}".strip()
            if error_code in {"context_length_exceeded", "max_tokens_exceeded"}:
                return True

    # Only inspect ambiguous text errors for likely request-validation statuses.
    if status_code not in (None, 400, 413):
        return False

    signals = [
        "maximum context length",
        "this model's maximum context",
        "context_length_exceeded",
        "max_tokens_exceeded",
        "prompt is too long",
        "maximum number of tokens",
        "too many tokens in the prompt",
    ]
    if any(signal in combined for signal in signals):
        return True

    # Fallback for phrasing variants while still requiring both context+limit semantics.
    return bool(
        re.search(
            r"(maximum|exceed(?:ed|s)?)\s+(?:context\s+length|number\s+of\s+tokens)",
            combined,
        )
        and ("context" in combined or "token" in combined)
    )


def should_exclude_failed_prompt(exc: Exception) -> bool:
    if is_context_length_error(exc) or is_auth_error(exc):
        return True

    # Any provider exception with an HTTP status means no assistant reply was produced.
    # Excluding that user prompt avoids accumulating unanswered turns in future context.
    if getattr(exc, "status_code", None) is not None:
        return True

    msg = str(exc).lower()
    if isinstance(exc, ValueError) and "too long for the selected model context" in msg:
        return True

    # Handle provider SDK errors that may not expose an HTTP status code.
    # Use module/class heuristics so this remains robust across SDK renames.
    class_name = exc.__class__.__name__.lower()
    class_module = exc.__class__.__module__.lower()
    if "openai" in class_module and class_name.endswith("error"):
        return True

    return False
