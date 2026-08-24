from backend.ingestion.chunking import chunk_lines


def test_empty_input_returns_no_chunks():
    assert chunk_lines([]) == []


def test_short_input_fits_in_one_chunk():
    lines = ["first line", "second line", "third line"]

    chunks = chunk_lines(lines, max_chars=1000)

    assert chunks == ["first line\nsecond line\nthird line"]


def test_splits_when_max_chars_exceeded():
    lines = ["a" * 40, "b" * 40, "c" * 40]

    chunks = chunk_lines(lines, max_chars=50, overlap_lines=0)

    assert len(chunks) == 3
    assert chunks[0] == "a" * 40
    assert chunks[1] == "b" * 40
    assert chunks[2] == "c" * 40


def test_overlap_carries_trailing_lines_into_next_chunk():
    lines = ["a" * 20, "b" * 20, "c" * 20, "d" * 20]

    chunks = chunk_lines(lines, max_chars=45, overlap_lines=1)

    assert chunks[0] == "a" * 20 + "\n" + "b" * 20
    # the last line of chunk 0 ("b"*20) carries into chunk 1
    assert chunks[1].startswith("b" * 20)
    assert chunks[1].endswith("c" * 20)


def test_oversized_single_line_becomes_its_own_chunk():
    lines = ["short", "x" * 5000, "short again"]

    chunks = chunk_lines(lines, max_chars=100, overlap_lines=0)

    assert "x" * 5000 in chunks
