"""下書き TSV の分布を、仕様の目安と並べて表示する（標準ライブラリのみ）。

使い方:
    python tools/draft_stats.py <draft.tsv> <part_stem> [--lines S|M|L]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_lib import (  # noqa: E402
    BAND_TARGETS,
    CHAR_RATIO_CODES,
    CLICHES,
    EMOTION_WORDS,
    PART_BY_STEM,
    final_punct,
    length_band,
    length_limits,
    load_draft,
    nonverbal_target,
    opener,
    punct_targets,
    sentences,
    strip_ruby,
    text_len,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("stem")
    ap.add_argument("--lines", help="この文長帯の行を一覧表示（S/M/L、ALL）")
    a = ap.parse_args()
    part = PART_BY_STEM[a.stem]
    rows = load_draft(Path(a.draft))
    n = len(rows)
    f = part.count / 200
    code = part.code
    print(f"行数 {n}（{part.count} 必要）")
    bc = Counter(length_band(code, text_len(r.text)) for r in rows)
    print("文長帯", {k: f"{bc.get(k,0)}（{lo*f:g}〜{hi*f:g}）" for k, (lo, hi) in BAND_TARGETS.items()})
    pc = Counter(final_punct(r.text) for r in rows)
    print("行末", {k: f"{pc.get(k,0)}（{lo*f:g}〜{hi*f:g}）" for k, (lo, hi) in punct_targets(code).items()})
    ic = Counter(r.intensity for r in rows)
    print("強度", dict(ic), f"（目安 {0.3*n:.0f}:{0.4*n:.0f}:{0.3*n:.0f}）")
    nv = Counter(r.nonverbal for r in rows)
    print("非言語", dict(nv), "目安（カテゴリ全体）", nonverbal_target(code))
    cc = Counter(r.character_style for r in rows)
    if code in CHAR_RATIO_CODES:
        print("話者", dict(cc), f"キャラ計 {n - cc.get('none',0)}（{0.4*n:.0f}〜{0.6*n:.0f}、1人 {5*f:g}〜{15*f:g}）")
    else:
        print("話者", dict(cc))
    print("ニュアンス", dict(Counter(r.nuance for r in rows)))
    pairs = Counter(r.near_pair_group for r in rows if r.near_pair_group)
    print("近接ペア", sum(1 for v in pairs.values() if v >= 2), "単独:", [g for g, v in pairs.items() if v < 2])
    print("感情語の行", sum(1 for r in rows if any(w in strip_ruby(r.text) for w in EMOTION_WORDS)))
    for c in CLICHES:
        v = sum(1 for r in rows if c in strip_ruby(r.text))
        if v > 3 * f:
            print(f"決まり文句「{c}」{v}")
    for o, v in Counter(opener(r.text) for r in rows).most_common(5):
        if o and v >= 3:
            print(f"書き出し「{o}」{v}")
    lo, hi = length_limits(code)
    cm = 5 if code == "ANNOUNCE" else 3
    for r in rows:
        L = text_len(r.text)
        ss = sentences(r.text)
        prob = []
        if not (lo <= L <= hi):
            prob.append(f"文字数{L}")
        if len(ss) > 3:
            prob.append(f"{len(ss)}文")
        if any(s.count("、") > cm for s in ss):
            prob.append("読点過多")
        if not final_punct(r.text):
            prob.append("行末記号なし")
        if prob:
            print("NG", prob, r.text)
    texts = Counter(r.text for r in rows)
    for t, v in texts.items():
        if v > 1:
            print("重複", t)
    if a.lines:
        for r in rows:
            b = length_band(code, text_len(r.text))
            if a.lines == "ALL" or b == a.lines:
                print(f"{b} {text_len(r.text):2d} {r.intensity:6s} {r.character_style:9s} {r.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
