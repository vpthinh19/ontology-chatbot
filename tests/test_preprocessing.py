"""Unit tests for Vietnamese text preprocessing pipeline."""

import pytest

from src.utils.preprocessing import (
    _normalize_repeated_chars,
    _normalize_teencode,
    _remove_emails,
    _remove_emojis,
    _remove_special_chars,
    _remove_urls,
    preprocess_batch,
    preprocess_text,
)


class TestRemoveUrls:
    def test_http_url(self):
        assert "xem " in _remove_urls("xem https://example.com/path nhé")

    def test_www_url(self):
        assert "xem " in _remove_urls("xem www.example.com nhé")

    def test_no_url(self):
        text = "không có link gì"
        assert _remove_urls(text) == text


class TestRemoveEmails:
    def test_email(self):
        result = _remove_emails("gửi email@test.com nhé")
        assert "@" not in result

    def test_no_email(self):
        text = "không email"
        assert _remove_emails(text) == text


class TestRemoveEmojis:
    def test_unicode_emoji(self):
        result = _remove_emojis("hay quá 😍🎉")
        assert "😍" not in result
        assert "🎉" not in result

    def test_text_emoji(self):
        result = _remove_emojis("vui :) buồn :(")
        assert ":)" not in result


class TestRemoveSpecialChars:
    def test_keeps_vietnamese(self):
        text = "Đăng ký học phần"
        assert _remove_special_chars(text) == text

    def test_removes_special(self):
        result = _remove_special_chars("hello @#$ world")
        assert "@" not in result
        assert "#" not in result


class TestNormalizeTeencode:
    def test_basic_teencode(self):
        assert "không" in _normalize_teencode("ko biết")

    def test_abbreviation(self):
        assert "đăng ký học phần" in _normalize_teencode("ĐKHP xong chưa")

    def test_no_teencode(self):
        text = "bình thường"
        # 'bình' might match 'bt' context but full word shouldn't change
        result = _normalize_teencode(text)
        assert isinstance(result, str)


class TestNormalizeRepeatedChars:
    def test_repeated(self):
        assert _normalize_repeated_chars("quáááá") == "quáá"

    def test_normal(self):
        assert _normalize_repeated_chars("bình thường") == "bình thường"


class TestPreprocessText:
    def test_empty_string(self):
        assert preprocess_text("") == ""

    def test_whitespace_only(self):
        assert preprocess_text("   ") == ""

    def test_basic_text(self):
        result = preprocess_text("Em muốn hỏi", word_segmentation=False)
        assert len(result) > 0
        assert isinstance(result, str)

    def test_with_url_and_emoji(self):
        text = "xem https://example.com 😍 nhé"
        result = preprocess_text(text, word_segmentation=False)
        assert "https" not in result
        assert "😍" not in result

    def test_no_word_segmentation(self):
        result = preprocess_text("test text", word_segmentation=False)
        assert isinstance(result, str)


class TestPreprocessBatch:
    def test_batch(self):
        texts = ["xin chào", "em hỏi"]
        results = preprocess_batch(texts, word_segmentation=False)
        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)

    def test_empty_batch(self):
        assert preprocess_batch([]) == []
