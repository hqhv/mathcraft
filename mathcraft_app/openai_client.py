from openai import OpenAI

from .config import MODEL_SUPPORTS_CUSTOM_TEMPERATURE
from .errors import auth_error_reason, auth_error_user_message, is_auth_error


def validate_openai_key(api_key: str) -> tuple[bool | None, str, str | None]:
    if not api_key:
        return None, "No API key provided.", None

    try:
        OpenAI(api_key=api_key).models.list()
        return True, "API key is valid.", "valid"
    except Exception as exc:
        if is_auth_error(exc):
            return False, auth_error_user_message(exc), auth_error_reason(exc)
        return None, f"Could not validate key due to a temporary connection/service issue: {exc}", None


def ask_openai(client: OpenAI, model: str, messages: list[dict], temperature: float) -> tuple[str, int, int]:
    request_kwargs = {
        "model": model,
        "messages": messages,
    }
    if MODEL_SUPPORTS_CUSTOM_TEMPERATURE.get(model, True):
        request_kwargs["temperature"] = temperature

    response = client.chat.completions.create(**request_kwargs)
    usage = response.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return response.choices[0].message.content or "", prompt_tokens, completion_tokens
