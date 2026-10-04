#!/usr/bin/env python3
"""前の段落を言い直しているだけの段落を報告する（cold-reader の型5の機械検査）。

型5＝結論の段落で前の段落を要約し直す失敗。読み手から見ると、新しく分かることがほとんど無い段落になる。

測るもの（段落ごと）:
- core_reuse: 段落の語のうち、それより前の段落で2回以上使われた語（＝文章の中心語）が占める割合。
  言い直しの段落は中心語を拾い集めて組み立てるので、この値が高くなる。判定にはこちらを使う。
- new_ratio: 段落の語のうち、それより前に一度も出ていない語の割合。参考値として出す。

語の取り出しは、漢字の連続・カタカナの連続・英単語をそれぞれ1語とみなす近似で行う。
形態素解析器に頼らず、標準ライブラリだけで動くようにするため。
ひらがなは助詞と活用語尾が大半で、どの段落にも出るので数えない。

較正（tests/fixtures の架空の題材: 自宅サーバーのバックアップについての質問への返事）:
- 正例（最後の段落が前の段落の要約。検出されるべき）:
  backup-v1-restating-last.md の段落7 が 0.43、backup-v2draft-restating-last.md の段落7 が 0.45。
- 負例（要約の段落を削り、新しい1点を理由の段落へ移した最終版。どれも検出されないべき）:
  backup-v2-final.md の判定対象の段落は 0.00 / 0.17 / 0.22 / 0.05 / 0.21（段落5 は3語で判定しない）。
  正例の下書きの、最後以外の段落も 0.21 以下。
しきい値は、正例の最小 0.43 と負例の最大 0.22 の間にある 0.40 のままで分かれた。
「新しい語の割合」は参考値で、箇条書きのように同じ語を繰り返す段落で下がるため判定には使わない。

既知の制限:
- 較正に使った正例は2本、負例の最終版は1本しかない。題材や文体が変われば、しきい値の置き直しが要りうる。
  正例の値（0.43）はしきい値に近いので、要約の段落が少し短いだけで見逃しうる。
- 同じ内容を別の語で言い換えた段落は検出できない。語が重なる言い直しだけを拾う。
- 語が15未満の短い段落（橋渡しの1文など）は値がぶれるので判定しない。
- 箇条書きのまとまりは1段落として扱う。
- 同じ用語を節ごとに使い回す参照用の文書（README など）では誤検知が増える。
- 検出は「疑い」まで。新しく言っていることが1つでもあれば、削らずにその1点を理由の段落へ移すのが直し方。

使い方:
    python3 restate_check.py FILE [--threshold 0.4] [--json]
    cat draft.md | python3 restate_check.py -
終了コード: 疑いのある段落が1つでもあれば 1、なければ 0。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass

DEFAULT_THRESHOLD = 0.40
# これより語の少ない段落は割合が1〜2語で大きく動くので判定から外す。
MIN_TOKENS = 15

_TOKEN = re.compile(r"[㐀-鿿々〆]+|[゠-ヿー]+|[A-Za-z][A-Za-z0-9_\-\.]*")


@dataclass
class ParagraphResult:
    """1段落ぶんの検査結果。"""

    index: int  # 1始まりの段落番号
    head: str  # 段落の書き出し（報告用）
    tokens: int
    core_reuse: float
    new_ratio: float
    flagged: bool


def split_paragraphs(text: str) -> list[str]:
    """空行で段落に分ける。見出し・コードブロック・水平線は本文ではないので除く。"""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    paras: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        lines = [ln for ln in lines if not re.match(r"^\s*(#{1,6}\s|-{3,}\s*$)", ln)]
        if lines:
            paras.append("\n".join(lines))
    return paras


def tokenize(paragraph: str) -> list[str]:
    """段落から内容語の近似を出現順に取り出す（重複あり）。"""
    return [t.lower() for t in _TOKEN.findall(paragraph)]


def check(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[ParagraphResult]:
    """各段落の core_reuse と new_ratio を計算し、言い直しの疑いがある段落に印をつける。"""
    seen: Counter[str] = Counter()
    results: list[ParagraphResult] = []
    for i, para in enumerate(split_paragraphs(text), start=1):
        toks = tokenize(para)
        n = len(toks)
        core = sum(1 for t in toks if seen[t] >= 2) / n if n else 0.0
        new = sum(1 for t in toks if t not in seen) / n if n else 1.0
        flagged = i > 1 and n >= MIN_TOKENS and core >= threshold
        head = para.replace("\n", " ")[:30]
        results.append(ParagraphResult(i, head, n, round(core, 2), round(new, 2), flagged))
        seen.update(toks)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="前の段落の言い直し（cold-reader 型5）を検出する")
    parser.add_argument("file", help="検査する Markdown。- で標準入力")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    results = check(text, args.threshold)
    flagged = [r for r in results if r.flagged]

    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "LOW " if r.flagged else "    "
            print(f"{mark}段落{r.index:>2}  中心語の再利用 {r.core_reuse:.2f}  新しい語 {r.new_ratio:.2f}"
                  f"  ({r.tokens:>3}語)  {r.head}")
        if flagged:
            print(f"\n[型5の疑い] {len(flagged)} 段落が、前の段落の中心語を拾い集めてできています。"
                  "この段落で初めて言っていることを1つ挙げてください。無ければ段落ごと削り、"
                  "あればその1点を理由を述べている段落へ移します。")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
