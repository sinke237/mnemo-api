"""
Unit tests for import service logic.
Focuses on CSV parsing, normalization, and deduplication.
"""

from mnemo.services.import_job import (
    _dedupe_rows,
    _is_header_row,
    _normalize_pair,
    _parse_csv_rows,
)


def test_is_header_row():
    assert _is_header_row(["question", "answer"]) is True
    assert _is_header_row(["Question", "Answer"]) is True
    assert _is_header_row(["  question  ", "  answer  "]) is True
    assert _is_header_row(["q", "a"]) is False
    assert _is_header_row(["question"]) is False
    assert _is_header_row([]) is False


def test_normalize_pair():
    assert _normalize_pair("  Q  ", "  A  ") == ("q", "a")
    assert _normalize_pair("Mixed Case", "Lower") == ("mixed case", "lower")


def test_parse_csv_rows_basic():
    text = "Q1,A1\nQ2,A2"
    rows, errors = _parse_csv_rows(text)
    assert len(rows) == 2
    assert rows[0] == ("Q1", "A1")
    assert rows[1] == ("Q2", "A2")
    assert not errors


def test_parse_csv_rows_with_header():
    text = "question,answer\nQ1,A1"
    rows, errors = _parse_csv_rows(text)
    assert len(rows) == 1
    assert rows[0] == ("Q1", "A1")
    assert not errors


def test_parse_csv_rows_different_delimiters():
    # Semicolon
    rows, _ = _parse_csv_rows("Q1;A1\nQ2;A2")
    assert len(rows) == 2
    assert rows[0] == ("Q1", "A1")

    # Tab
    rows, _ = _parse_csv_rows("Q1\tA1\nQ2\tA2")
    assert len(rows) == 2
    assert rows[0] == ("Q1", "A1")


def test_parse_csv_rows_empty_and_invalid():
    # Empty
    rows, errors = _parse_csv_rows("")
    assert not rows
    assert "CSV file is empty." in errors

    # Blank lines
    rows, errors = _parse_csv_rows("\n\n  \n")
    assert not rows

    # Missing columns
    rows, errors = _parse_csv_rows("OnlyOneColumn\nValid,Pair")
    assert len(rows) == 1
    assert any("fewer than 2 columns" in e for e in errors)

    # Blank values
    rows, errors = _parse_csv_rows(",\nValid,Pair")
    assert len(rows) == 1
    # Row 1 is "," -> ["", ""] -> blank question or answer
    # The current implementation of _parse_csv_rows for Row 1 (if not header)
    # checks if question and answer are truthy after strip().
    # "," results in ["", ""] which fails `if question and answer:`
    # BUT it doesn't add an error if it's just an empty row.
    # Wait, let's check the code again.
    # if not first_row or all(not cell.strip() for cell in first_row): pass
    # So ["" , ""] is skipped without error.
    assert not any("blank question or answer" in e for e in errors)


def test_dedupe_rows():
    rows = [("Q1", "A1"), ("q1", "a1"), ("Q2", "A2")]
    existing = {("q1", "a1")}

    unique, skipped = _dedupe_rows(rows, existing)

    # Q1,A1 is same as q1,a1 (normalized), so it should be skipped
    # q1,a1 is same as existing, so it should be skipped
    # Q2,A2 is new
    assert len(unique) == 1
    assert unique[0] == ("Q2", "A2")
    assert skipped == 2


def test_parse_csv_rows_quoted():
    # Test RFC 4180: embedded commas and actual newlines within quoted fields
    text = '"Question with, comma","Answer with\nnewline"\n"Simple","Pair"'
    rows, errors = _parse_csv_rows(text)
    assert len(rows) == 2
    assert rows[0] == ("Question with, comma", "Answer with\nnewline")
    assert rows[1] == ("Simple", "Pair")
    assert not errors
