#!/usr/bin/env python3
"""日本語の文章の改行と空行を検査し、直す。

決まりは2つ（SKILL.md）:
  1. 文ごとに改行する（句点「。」「！」「？」の後に同じ行で次の文を続けない）
  2. 役割の塊ごとに空行を入れる（これは判断なので、ここでは疑わしい段落を知らせるだけ）

対象は地の文の段落と引用（> ）だけ。コードブロック・表・見出し・箇条書き・HTML・front matter は触らない。
箇条書きの中で改行すると、Discord では項目の外に出たように見え、md では続きの行の字下げが要るため。

使い方:
  layout.py FILE           検査だけ（違反があれば終了コード 1）
  layout.py FILE --fix     文ごとの改行を入れて上書きする（空行は入れない）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 文の終わり。閉じかっこが続くときは、かっこの後ろで切る（「〜です。」と書いた → 「」の中では切らない）
ENDERS = "。！？!?"
OPEN = "「『（(【〔［[〈《"
CLOSE = "」』）)】〕］]〉》"
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
SKIP_LINE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|\||<|:::|\$\$|-#\s)")
QUOTE = re.compile(r"^(\s*(?:>\s?)+)(.*)$")
# 1段落にこれより多い文があれば、役割が2つ以上混ざっていないか確かめるよう知らせる
MANY_SENTENCES = 4


def split_sentences(text: str) -> list[str]:
    """1行を文に分ける。かっこの中の句点では切らない。インラインコードの中でも切らない。"""
    out: list[str] = []
    depth = 0
    in_code = False
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "`":
            in_code = not in_code
        elif not in_code:
            if ch in OPEN:
                depth += 1
            elif ch in CLOSE and depth > 0:
                depth -= 1
                # 丸かっこが文を丸ごと包んでいる（（補足です。））ときは、閉じかっこの後で文が終わる。
                # かぎかっこは「〜です。」と書いた、のように後ろへ続くことが多いので切らない
                if depth == 0 and ch in "）)" and i > 0 and text[i - 1] in ENDERS:
                    out.append(text[start : i + 1].strip())
                    start = i + 1
            elif ch in ENDERS and depth == 0:
                j = i + 1
                # 「。」の後に続く閉じかっこ・連続する！？は同じ文に含める
                while j < n and (text[j] in ENDERS or text[j] in CLOSE):
                    j += 1
                # 半角の ! ? は英語の文中にも出る。後ろが空白か行末のときだけ文の終わりとみなす
                if ch in "!?" and j < n and not text[j].isspace():
                    i += 1
                    continue
                out.append(text[start:j].strip())
                start = j
                i = j
                continue
        i += 1
    rest = text[start:].strip()
    if rest:
        out.append(rest)
    # 記号だけの切れ端（斜体の閉じ * など）は文に数えず、直前の文に付ける
    merged: list[str] = []
    for s in out:
        if merged and not re.search(r"\w", s):
            merged[-1] += s
        elif s:
            merged.append(s)
    return merged


def iter_blocks(lines: list[str]):
    """(行番号, 行, 対象かどうか) を返す。front matter とコードブロックの中は対象外。"""
    fence = None
    front = bool(lines) and lines[0].strip() == "---"
    for no, line in enumerate(lines):
        if front:
            if no > 0 and line.strip() in ("---", "..."):
                front = False
            yield no, line, False
            continue
        m = FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            yield no, line, False
            continue
        if m:
            fence = m.group(1)
            yield no, line, False
            continue
        if not line.strip() or SKIP_LINE.match(line):
            yield no, line, False
            continue
        yield no, line, True


def check(lines: list[str]) -> list[str]:
    problems: list[str] = []
    para: list[int] = []  # いまの段落の文の数を数えるための行番号
    count = 0

    def close_para():
        nonlocal count
        if count > MANY_SENTENCES and para:
            problems.append(f"L{para[0] + 1}: 段落に {count} 文ある。役割が2つ以上混ざっていないか確かめ、混ざっていれば空行で分ける")
        para.clear()
        count = 0

    for no, line, target in iter_blocks(lines):
        if not target:
            if not line.strip() or SKIP_LINE.match(line):
                close_para()
            continue
        q = QUOTE.match(line)
        body = q.group(2) if q else line
        sents = split_sentences(body)
        if len(sents) > 1:
            problems.append(f"L{no + 1}: 1行に {len(sents)} 文ある（文ごとに改行）: {sents[0][:30]}…")
        para.append(no)
        count += len(sents)
    close_para()
    return problems


def fix(lines: list[str]) -> list[str]:
    out: list[str] = []
    for _no, line, target in iter_blocks(lines):
        if not target:
            out.append(line)
            continue
        q = QUOTE.match(line)
        prefix = q.group(1) if q else ""
        body = q.group(2) if q else line
        sents = split_sentences(body)
        if len(sents) <= 1:
            out.append(line)
            continue
        out.extend(prefix + s for s in sents)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--fix", action="store_true", help="文ごとの改行を入れて上書きする")
    args = ap.parse_args()
    path = Path(args.file)
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if args.fix:
        fixed = "\n".join(fix(lines))
        if fixed != text:
            path.write_text(fixed, encoding="utf-8")
            print(f"直した: {path}")
        lines = fixed.split("\n")
    problems = check(lines)
    for p in problems:
        print(p)
    if not problems:
        print("指摘なし")
    # 文ごとの改行の違反だけを失敗にする。段落の文の数は知らせるだけ
    return 1 if any("文ごとに改行" in p for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
