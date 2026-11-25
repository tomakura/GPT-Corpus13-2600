"""下書き TSV を「先頭から録るほど効率がよい並び」に並べ替え、ID を振って3ファイルを書き出す。

使い方:
    python tools/order_lines.py <draft.tsv> <part_stem> <model_dir> [--no-mora] [--seed N]
    例: python tools/order_lines.py drafts/01_JOY.tsv 01_JOY Claude-Opus-5.5

下書き TSV の列（UTF-8、タブ区切り）:
    character_style, nuance, intensity, nonverbal, near_pair_group, scene, text

並べ方（貪欲法）:
- 各位置で、ニュアンス・話者・強度・文長帯・行末記号・非言語の「期待数との差（不足分）」が
  最も大きい行を選ぶ。どこで切っても各属性がファイル全体の割合に近くなる。
- pyopenjtalk が使える環境では、まだ少ないモーラを含む行を優先する（--no-mora で無効）。
- 同じ人物（none 以外）・同じ文長帯の3連続、近接ペアの5行以内の接近、同じ書き出しの連続を避ける。
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_lib import PART_BY_STEM, Row, final_punct, length_band, load_draft, opener, text_len, write_part  # noqa: E402

WEIGHTS = {"nuance": 1.0, "spk": 1.0, "intensity": 0.7, "band": 0.8, "punct": 0.8, "nv": 0.8}


def features(r: Row, code: str) -> dict[str, str]:
    return {
        "nuance": r.nuance,
        "spk": r.character_style,
        "intensity": r.intensity,
        "band": length_band(code, text_len(r.text)),
        "punct": final_punct(r.text),
        "nv": "nv" if r.nonverbal != "none" else "-",
    }


def order(rows: list[Row], code: str, moras: list[list[str]] | None, seed: int = 0) -> list[Row]:
    rnd = random.Random(seed)
    n = len(rows)
    feats = [features(r, code) for r in rows]
    totals = {d: Counter(f[d] for f in feats) for d in WEIGHTS}
    counts = {d: Counter() for d in WEIGHTS}
    mora_seen: Counter = Counter()
    mora_total: Counter = Counter()
    if moras:
        for ms in moras:
            mora_total.update(set(ms))
    placed: list[int] = []
    remaining = set(range(n))
    jitter = {i: rnd.random() * 1e-3 for i in range(n)}

    def violates(i: int, strict: bool) -> bool:
        f = feats[i]
        if len(placed) >= 2:
            a, b = feats[placed[-1]], feats[placed[-2]]
            if f["spk"] != "none" and a["spk"] == b["spk"] == f["spk"]:
                return True
            if strict and a["band"] == b["band"] == f["band"]:
                return True
        g = rows[i].near_pair_group
        if g and strict:
            for j in placed[-5:]:
                if rows[j].near_pair_group == g:
                    return True
        if strict and placed and opener(rows[i].text) and opener(rows[i].text) == opener(rows[placed[-1]].text):
            return True
        return False

    for k in range(n):
        best, best_score = None, -1e18
        for strict in (True, False):
            for i in remaining:
                if violates(i, strict):
                    continue
                f = feats[i]
                s = 0.0
                for d, w in WEIGHTS.items():
                    v = f[d]
                    expected = totals[d][v] / n * (k + 1)
                    s += w * (expected - counts[d][v])
                if moras:
                    rare = [m for m in set(moras[i]) if mora_seen[m] < 2]
                    # 全体でも少ないモーラほど価値が高い
                    s += 0.5 * sum(1.0 / max(1, mora_total[m]) ** 0.5 for m in rare)
                s += jitter[i]
                if s > best_score:
                    best, best_score = i, s
            if best is not None:
                break
        assert best is not None
        placed.append(best)
        remaining.discard(best)
        for d in WEIGHTS:
            counts[d][feats[best][d]] += 1
        if moras:
            mora_seen.update(set(moras[best]))
    return [rows[i] for i in placed]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("stem")
    ap.add_argument("model_dir")
    ap.add_argument("--no-mora", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    part = PART_BY_STEM[a.stem]
    rows = load_draft(Path(a.draft))
    if len(rows) != part.count:
        print(f"ERROR: 下書きの行数 {len(rows)}（{part.count} 必要）")
        return 1
    moras = None
    if not a.no_mora:
        try:
            import sbv2_esd

            moras = [sbv2_esd.moras_of(sbv2_esd.resolve_ruby(r.text)[0]) for r in rows]
        except Exception as e:  # pyopenjtalk がない環境
            print(f"(モーラを使わずに並べる: {e})")
    ordered = order(rows, part.code, moras, a.seed)
    for i, r in enumerate(ordered, 1):
        r.id = f"{part.prefix}_{i:03d}"
    write_part(Path(a.model_dir), part, ordered)
    print(f"{part.stem}: {len(ordered)} 行を書き出した")
    return 0


if __name__ == "__main__":
    sys.exit(main())
