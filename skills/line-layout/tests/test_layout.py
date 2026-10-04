"""layout.py のテスト。

実行（リポジトリの直下で）: python3 -m unittest discover -s skills/line-layout/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from layout import check, fix, split_sentences  # noqa: E402


class SplitTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_sentences("一つ目です。二つ目です。"), ["一つ目です。", "二つ目です。"])

    def test_quote_brackets_are_not_split(self):
        self.assertEqual(split_sentences("「保管庫です。」と書いた。次。"), ["「保管庫です。」と書いた。", "次。"])

    def test_closing_bracket_stays_with_sentence(self):
        self.assertEqual(split_sentences("（補足です。）次の文。"), ["（補足です。）", "次の文。"])

    def test_inline_code_is_not_split(self):
        self.assertEqual(split_sentences("`a。b` を使う。次。"), ["`a。b` を使う。", "次。"])

    def test_ascii_bang_inside_word(self):
        self.assertEqual(split_sentences("x!=y を比べる。"), ["x!=y を比べる。"])

    def test_markup_only_fragment_joins_previous(self):
        self.assertEqual(split_sentences("一文。*"), ["一文。*"])

    def test_trailing_fragment(self):
        self.assertEqual(split_sentences("一文。続き"), ["一文。", "続き"])


class FixTest(unittest.TestCase):
    def test_paragraph_and_quote_are_split(self):
        src = ["一つ目。二つ目。", "", "> 引用一。引用二。"]
        self.assertEqual(fix(src), ["一つ目。", "二つ目。", "", "> 引用一。", "> 引用二。"])

    def test_untouched_blocks(self):
        src = ["---", "a: 一。二。", "---", "```", "一。二。", "```", "- 項目一。項目二。", "| 表一。表二。 |", "## 見出し。続き。"]
        self.assertEqual(fix(src), src)

    def test_check_reports_line_and_many_sentences(self):
        probs = check(["一。二。", "三。", "四。", "五。"])
        self.assertTrue(any("L1" in p and "文ごとに改行" in p for p in probs))
        self.assertTrue(any("役割" in p for p in probs))

    def test_check_clean(self):
        self.assertEqual(check(["一。", "二。", "", "三。"]), [])


if __name__ == "__main__":
    unittest.main()
