"""restate_check.py の較正テスト。

架空の題材（自宅サーバーのバックアップについての質問への返事）の下書きを正解データにする。
最後の段落が前の段落の要約になっている下書き2本ではその段落が検出され、
要約の段落を削った最終版ではどの段落も検出されないことを確かめる。
実行（リポジトリの直下で）: python3 -m unittest discover -s skills/cold-reader/tests
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import restate_check  # noqa: E402

FIX = HERE / "fixtures"


def flagged_indexes(name: str) -> list[int]:
    text = (FIX / name).read_text(encoding="utf-8")
    return [r.index for r in restate_check.check(text) if r.flagged]


class CalibrationTest(unittest.TestCase):
    def test_restating_last_paragraph_is_flagged_in_v1(self):
        # 第1版。7段落目が前の段落の要約で、新しい点は「別の筐体にあるので残る」の1つだけ。
        self.assertEqual(flagged_indexes("backup-v1-restating-last.md"), [7])

    def test_restating_last_paragraph_is_flagged_in_v2_draft(self):
        # 第2版の下書き。型1〜4は直したが、7段落目の要約は残っている。
        self.assertEqual(flagged_indexes("backup-v2draft-restating-last.md"), [7])

    def test_final_v2_has_no_flags(self):
        # 最終版。要約の段落を削り、新しい1点を1段落目へ移した。
        self.assertEqual(flagged_indexes("backup-v2-final.md"), [])


class UnitTest(unittest.TestCase):
    def test_first_paragraph_never_flagged(self):
        text = "保管庫の実体はフォルダです。保管庫の実体はフォルダです。保管庫の実体はフォルダです。" * 3
        self.assertEqual([r.flagged for r in restate_check.check(text)], [False])

    def test_short_bridge_paragraph_not_judged(self):
        text = "スナップショットは毎晩作ります。スナップショットはNASに置きます。スナップショット NAS NAS 毎晩\n\n残りのスナップショットはNASにあります。"
        results = restate_check.check(text)
        self.assertFalse(results[1].flagged)

    def test_hiragana_is_not_counted(self):
        self.assertEqual(restate_check.tokenize("これはそうです。"), [])
        self.assertEqual(restate_check.tokenize("保管庫はNASのフォルダ"), ["保管庫", "nas", "フォルダ"])


if __name__ == "__main__":
    unittest.main()
