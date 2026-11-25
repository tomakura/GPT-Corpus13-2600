"""SBV2 と同じ読み推定（pyopenjtalk）で、モーラの出現数を数える。

使い方:
    python tools/coverage.py Claude-Opus-5.5 [--head 100] [--min 3] [--codes JOY ANGRY ...]

- 全体: SBV2 のモーラ表にある各モーラの出現数（行数ではなく出現回数）
- 先頭: 各ファイルの先頭 N 行だけを合わせた範囲での出現数
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sbv2_esd  # noqa: E402
from corpus_lib import PARTS, load_part  # noqa: E402

# 実際の日本語でまず出ない、表の互換用のモーラ
# （ヴ系は SBV2 では b の音素に読み替えられる。リェ・テャ などは外来語でもほぼ使われない表記上のモーラ）
RARE_OK = {"ヴォ", "ヴェ", "ヴィ", "ヴァ", "ヴ", "グヮ", "クヮ", "ヴョ", "ヴュ", "ヴャ", "ヰ", "ヱ", "ヮ", "ヂ", "ヅ", "ヲ",
           "リェ", "ミェ", "ピェ", "ビェ", "ヒェ", "ニェ", "ギェ", "キェ", "デョ", "デャ", "テョ", "テャ", "テュ",
           "ドゥ", "ツィ", "ツェ", "ツォ", "スィ", "ズィ"}


def inventory() -> list[str]:
    inv = []
    seen = set()
    for kata, ph in sbv2_esd.MORA_KATA_TO_MORA_PHONEMES.items():
        label = sbv2_esd.PHONEMES_TO_KATA[ph]
        if label not in seen:
            seen.add(label)
            inv.append(label)
    return inv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("--head", type=int, default=100)
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--codes", nargs="*")
    a = ap.parse_args()
    md = Path(a.model_dir)
    total, head = Counter(), Counter()
    nlines = 0
    for p in PARTS:
        if a.codes and p.code not in a.codes:
            continue
        if not (md / f"{p.stem}.txt").exists():
            continue
        rows = load_part(md, p)
        for i, r in enumerate(rows):
            ms = sbv2_esd.moras_of(sbv2_esd.resolve_ruby(r.text)[0])
            ms = [m for m in ms if m != "ー"]
            total.update(ms)
            if i < a.head:
                head.update(ms)
            nlines += 1
    inv = inventory()
    print(f"行数 {nlines}、モーラ表 {len(inv)} 種")
    lack = [(m, total[m]) for m in inv if total[m] < a.min and m not in RARE_OK]
    lack_rare = [(m, total[m]) for m in inv if total[m] < 1 and m in RARE_OK]
    lack_head = [(m, head[m]) for m in inv if head[m] < 1 and m not in RARE_OK]
    print(f"全体で {a.min} 回未満（通常モーラ）: {len(lack)} 種")
    print("  " + " ".join(f"{m}:{c}" for m, c in lack))
    print(f"全体で 0 回（まれなモーラ・参考）: " + " ".join(m for m, _ in lack_rare))
    print(f"先頭 {a.head} 行の範囲で 0 回（通常モーラ）: {len(lack_head)} 種")
    print("  " + " ".join(m for m, _ in lack_head))
    print("出現の少ない順（上位40）: " + " ".join(f"{m}:{total[m]}" for m in sorted([m for m in inv if m not in RARE_OK], key=lambda m: total[m])[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
