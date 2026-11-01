"""
Purpose: Produce safe, readable Telegram messages for executive tax reporting.
Sample input: Registry response text.
Output: Ordered message chunks below Telegram's message-size limit.
Dependencies: Python standard library.
Architecture: tax_service / AnythingLLM -> response_formatter -> Telegram.
"""


def split_telegram_message(message: str, max_length: int = 3900) -> list[str]:
    """Split text without dropping content or exceeding the configured message size.

    Long lines are split at word boundaries where possible and hard-split only
    when a single token exceeds the available Telegram message length.
    """
    if max_length < 100:
        raise ValueError("max_length must be at least 100 characters.")
    text = (message or "").strip()
    if not text:
        return ["No response was generated."]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for original_line in text.splitlines():
        line = original_line.rstrip()
        if not line:
            if current and not current.endswith("\n\n"):
                current += "\n"
            continue

        while len(line) > max_length:
            if current:
                flush()
            split_at = line.rfind(" ", 0, max_length + 1)
            if split_at <= 0:
                split_at = max_length
            chunks.append(line[:split_at].rstrip())
            line = line[split_at:].lstrip()

        candidate = line if not current else current + "\n" + line
        if len(candidate) > max_length:
            flush()
            current = line
        else:
            current = candidate

    flush()
    return chunks or ["No response was generated."]
