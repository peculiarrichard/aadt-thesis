DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_LINES = 2


def chunk_lines(
    lines: list[str],
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_lines: int = DEFAULT_OVERLAP_LINES,
) -> list[str]:
    """Group consecutive lines into chunks up to max_chars.

    Carries the last overlap_lines lines of each chunk into the next chunk, so retrieval
    context isn't lost at a chunk boundary. A single line longer than max_chars becomes
    its own oversized chunk rather than being split mid-line.
    """
    if not lines:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        added_len = len(line) + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            chunks.append("\n".join(current))
            current = current[-overlap_lines:] if overlap_lines else []
            current_len = sum(len(item) for item in current) + max(len(current) - 1, 0)
        current.append(line)
        current_len += len(line) + (1 if len(current) > 1 else 0)

    if current:
        chunks.append("\n".join(current))

    return chunks
