import pytest

from app.core.errors import AppError
from app.rag.chunking import chunk_text, parse_document


def test_parse_txt():
    text = parse_document("notes.txt", b"Hello world. This is a plain text document.")
    assert "Hello world" in text


def test_parse_unsupported_extension_raises():
    with pytest.raises(AppError):
        parse_document("archive.zip", b"fake bytes")


def test_parse_empty_file_raises():
    with pytest.raises(AppError):
        parse_document("empty.txt", b"   ")


def test_chunk_text_respects_size_limit():
    long_text = "\n\n".join([f"Paragraph number {i} with some extra words to pad it out a bit." for i in range(200)])
    chunks = chunk_text(long_text, chunk_size=300, overlap=30)
    assert len(chunks) > 1
    assert all(len(c.text) <= 330 for c in chunks)  # small slack for boundary edge cases


def test_chunk_text_short_input_single_chunk():
    chunks = chunk_text("Just one short paragraph.")
    assert len(chunks) == 1
    assert chunks[0].index == 0
