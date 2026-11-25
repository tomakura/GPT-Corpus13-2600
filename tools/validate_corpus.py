"""コーパス仕様 v3 の検証（標準ライブラリのみ）。

使い方:
    python tools/validate_corpus.py Claude-Opus-5.5            # 全カテゴリ
    python tools/validate_corpus.py Claude-Opus-5.5 JOY         # 1カテゴリ（サブスタイルを含む）
    python tools/validate_corpus.py Claude-Opus-5.5 --cross     # カテゴリをまたいだ類似文も調べる

ERROR は「必ず満たす」条件の違反、WARN は数値の目安からの逸脱。
ERROR が1件でもあれば終了コード 1 を返す。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_lib import (  # noqa: E402
    ALLOWED_RE,
    ANY_PAREN_RE,
    BAND_TARGETS,
    CHAR_RATIO_CODES,
    CLICHES,
    CSV_HEADER,
    EMOTION_WORDS,
    EMOTIONAL,
    INTENSITIES,
    NONVERBAL_TOKENS,
    NONVERBAL_TYPES,
    PARTS,
    Part,
    char_ngrams,
    final_punct,
    jaccard,
    length_band,
    length_limits,
    load_part,
    nonverbal_target,
    opener,
    punct_targets,
    read_cp932_lines,
    sentences,
    strip_ruby,
    text_len,
)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.infos: list[str] = []

    def err(self, m: str) -> None:
        self.errors.append(m)

    def warn(self, m: str) -> None:
        self.warns.append(m)

    def info(self, m: str) -> None:
        self.infos.append(m)


def character_ids(model_dir: Path) -> set[str]:
    p = model_dir / "CHARACTERS.md"
    if not p.exists():
        return set()
    ids = set()
    in_cast = False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_cast = "キャスト" in line
        if in_cast:
            m = re.match(r"^\|\s*`?([a-z][a-z0-9_]*)`?\s*\|", line)
            if m and m.group(1) not in ("id",):
                ids.add(m.group(1))
    return ids


def nonverbal_in_text(text: str) -> str | None:
    t = strip_ruby(text)
    for kind, toks in NONVERBAL_TOKENS.items():
        for tok in toks:
            if tok in t:
                return kind
    return None


def check_files(model_dir: Path, part: Part, rep: Report) -> bool:
    ok = True
    for suffix in (".txt", "_IDs.txt", "_AUDIT.csv"):
        p = model_dir / f"{part.stem}{suffix}"
        if not p.exists():
            rep.err(f"{part.stem}: {p.name} がない")
            ok = False
            continue
        try:
            lines, raw = read_cp932_lines(p)
        except UnicodeDecodeError as e:
            rep.err(f"{p.name}: CP932 で読めない: {e}")
            ok = False
            continue
        if b"\n" in raw.replace(b"\r\n", b""):
            rep.err(f"{p.name}: CRLF 以外の改行がある")
        lines = [l for l in lines if l]
        want = part.count + (1 if suffix == "_AUDIT.csv" else 0)
        if len(lines) != want:
            rep.err(f"{p.name}: 行数 {len(lines)}（{want} 必要）")
    return ok


def check_part(model_dir: Path, part: Part, rep: Report, chars: set[str]) -> list:
    if not check_files(model_dir, part, rep):
        return []
    rows = load_part(model_dir, part)
    want_ids = [f"{part.prefix}_{i:03d}" for i in range(1, part.count + 1)]
    ids = [r.id for r in rows]
    if ids != want_ids:
        rep.err(f"{part.stem}: ID が連番 {want_ids[0]}〜{want_ids[-1]} になっていない")
    id_lines, _ = read_cp932_lines(model_dir / f"{part.stem}_IDs.txt")
    if [l for l in id_lines if l] != ids:
        rep.err(f"{part.stem}: 本文と IDs の ID が一致しない")
    csv_lines, _ = read_cp932_lines(model_dir / f"{part.stem}_AUDIT.csv")
    if csv_lines[0] != ",".join(CSV_HEADER):
        rep.err(f"{part.stem}: CSV ヘッダが違う: {csv_lines[0]}")
    csv_ids = [l.split(",", 1)[0] for l in csv_lines[1:] if l]
    if csv_ids != ids:
        rep.err(f"{part.stem}: 本文と CSV の ID が一致しない")

    lo, hi = length_limits(part.code)
    comma_max = 5 if part.code == "ANNOUNCE" else 3
    prev_spk: list[str] = []
    prev_band: list[str] = []
    for r in rows:
        t = r.text
        n = text_len(t)
        tag = f"{r.id}"
        if not (lo <= n <= hi):
            rep.err(f"{tag}: 文字数 {n}（{lo}〜{hi}）: {t}")
        if not ALLOWED_RE.match(t):
            bad = sorted({c for c in t if not ALLOWED_RE.match(c)})
            rep.err(f"{tag}: 使えない文字 {bad}: {t}")
        if re.search(r"([、。！？…ー])\1\1", t):
            rep.err(f"{tag}: 同じ記号の3連続: {t}")
        if t.startswith("…"):
            rep.err(f"{tag}: 行頭に「…」を置かない（SBV2 の読み推定で警告が出る）: {t}")
        if "……" in t:
            rep.err(f"{tag}: 「……」は使わない: {t}")
        if "！？" in t:
            rep.err(f"{tag}: 「！？」ではなく「？！」: {t}")
        if ANY_PAREN_RE.search(strip_ruby(t)):
            rep.err(f"{tag}: ルビの書式が不正（カッコの前に漢字・数字がない、または中がカタカナでない）: {t}")
        ss = sentences(t)
        if len(ss) > 3:
            rep.err(f"{tag}: 文が {len(ss)} 個（3まで）: {t}")
        for s in ss:
            if s.count("、") > comma_max:
                rep.err(f"{tag}: 1文の読点が {s.count('、')} 個（{comma_max}まで）: {t}")
        fp = final_punct(t)
        if not fp:
            rep.err(f"{tag}: 行末が記号で終わっていない: {t}")
        if r.punctuation != fp:
            rep.err(f"{tag}: CSV punctuation '{r.punctuation}' と行末 '{fp}' が違う")
        if r.intensity not in INTENSITIES:
            rep.err(f"{tag}: intensity が不正: {r.intensity}")
        if r.nonverbal not in NONVERBAL_TYPES:
            rep.err(f"{tag}: nonverbal が不正: {r.nonverbal}")
        cs = r.character_style
        if cs != "none" and chars and cs not in chars:
            rep.err(f"{tag}: character_style '{cs}' が CHARACTERS.md にない")
        if part.code == "ANNOUNCE" and cs != "none":
            rep.err(f"{tag}: ANNOUNCE の character_style は none")
        if "," in r.scene:
            rep.err(f"{tag}: scene に半角カンマ")
        if not r.scene or not r.nuance:
            rep.warn(f"{tag}: scene または nuance が空")
        nv = nonverbal_in_text(t)
        if r.nonverbal != "none" and nv is None:
            rep.warn(f"{tag}: nonverbal={r.nonverbal} だが本文にホワイトリストの表記がない: {t}")
        # 連続
        band = length_band(part.code, n)
        if cs != "none" and len(prev_spk) >= 2 and prev_spk[-1] == prev_spk[-2] == cs:
            rep.err(f"{tag}: 同じ人物 {cs} が3行連続")
        if len(prev_band) >= 2 and prev_band[-1] == prev_band[-2] == band:
            rep.warn(f"{tag}: 同じ文長帯 {band} が3行連続")
        prev_spk.append(cs)
        prev_band.append(band)
    return rows


def range_warn(rep: Report, label: str, val: int, lo: float, hi: float) -> None:
    if not (lo <= val <= hi):
        rep.warn(f"{label}: {val}（目安 {lo:g}〜{hi:g}）")


def check_category(code: str, parts: list[Part], rows_by_part: dict, rep: Report) -> None:
    rows = [r for p in parts for r in rows_by_part.get(p.stem, [])]
    if not rows:
        return
    total = len(rows)
    f = total / 200
    # 行末記号
    pc = Counter(final_punct(r.text) for r in rows)
    for k, (lo, hi) in punct_targets(code).items():
        range_warn(rep, f"{code}: 行末「{k}」", pc.get(k, 0), lo * f, hi * f)
    # 文長
    bc = Counter(length_band(code, text_len(r.text)) for r in rows)
    for k, (lo, hi) in BAND_TARGETS.items():
        range_warn(rep, f"{code}: 文長帯 {k}", bc.get(k, 0), lo * f, hi * f)
    # 強度
    ic = Counter(r.intensity for r in rows)
    for k, (lo, hi) in {"weak": (0.22, 0.38), "mid": (0.30, 0.50), "strong": (0.22, 0.38)}.items():
        range_warn(rep, f"{code}: 強度 {k}", ic.get(k, 0), lo * total, hi * total)
    # 非言語
    nvl = [r for r in rows if r.nonverbal != "none"]
    lo, hi = nonverbal_target(code)
    range_warn(rep, f"{code}: 非言語の行数", len(nvl), lo, hi)
    if nvl:
        laughs_end = sum(1 for r in nvl if r.nonverbal == "laugh" and re.search(r"(ふふっ|ふふ|うふふ|くすっ|くすくす|あははっ|あはは|はははっ|ははっ|えへへ|へへっ|へへ|くくっ|ふっ|はっ)[。！？…]+$", strip_ruby(r.text)))
        if laughs_end * 2 < len(nvl):
            rep.warn(f"{code}: 文末の笑いが非言語の半分未満（{laughs_end}/{len(nvl)}）")
    # キャラ
    if code in CHAR_RATIO_CODES:
        cc = Counter(r.character_style for r in rows if r.character_style != "none")
        nchar = sum(cc.values())
        range_warn(rep, f"{code}: キャラ台詞の行数", nchar, 0.4 * total, 0.6 * total)
        for c, v in cc.items():
            range_warn(rep, f"{code}: 人物 {c} の行数", v, 5 * f, 15 * f)
    # 決まり文句・書き出し
    for c in CLICHES:
        v = sum(1 for r in rows if c in strip_ruby(r.text))
        if v > 5 * f:
            rep.warn(f"{code}: 決まり文句「{c}」{v} 回（{5 * f:g} まで）")
    oc = Counter(opener(r.text) for r in rows)
    olim = (8 if code == "ANNOUNCE" else 5) * f  # ANNOUNCE は定型の書き出しが本物らしさの一部
    for o, v in oc.items():
        if o and v > olim:
            rep.warn(f"{code}: 書き出し「{o}」{v} 回（{olim:g} まで）")
    if code in EMOTIONAL or code in ("WHISPER", "LAZY"):
        ev = sum(1 for r in rows if any(w in strip_ruby(r.text) for w in EMOTION_WORDS))
        if ev > 0.35 * total:
            rep.warn(f"{code}: 感情語を含む行 {ev}（3割程度まで）")
    # 近接ペア
    groups = Counter(r.near_pair_group for r in rows if r.near_pair_group)
    pairs = sum(1 for g, v in groups.items() if v >= 2)
    singles = [g for g, v in groups.items() if v < 2]
    if singles:
        rep.warn(f"{code}: 相手のいない近接ペア {singles}")
    range_warn(rep, f"{code}: 近接ペア数", pairs, 10 * f, 20 * f)
    # 類似文
    grams = [(r.id, char_ngrams(r.text), r.text) for r in rows]
    for i in range(len(grams)):
        for j in range(i + 1, len(grams)):
            s = jaccard(grams[i][1], grams[j][1])
            if s >= 0.5:
                rep.warn(f"{code}: 類似 {s:.2f} {grams[i][0]}「{grams[i][2]}」/ {grams[j][0]}「{grams[j][2]}」")
    # 先頭の偏り（ニュアンスと人物）
    for p in parts:
        prow = rows_by_part.get(p.stem, [])
        if len(prow) < 50:
            continue
        for key in ("nuance", "character_style"):
            allc = Counter(getattr(r, key) for r in prow)
            head = Counter(getattr(r, key) for r in prow[: min(50, len(prow) // 2)])
            hn = sum(head.values())
            for k, v in allc.items():
                exp = v / len(prow) * hn
                if exp >= 3 and head.get(k, 0) < exp * 0.4:
                    rep.warn(f"{p.stem}: 先頭 {hn} 行で {key}={k} が少ない（{head.get(k, 0)}/期待 {exp:.1f}）")
    rep.info(f"{code}: {total} 行 / 行末 {dict(pc)} / 文長 {dict(bc)} / 強度 {dict(ic)} / 非言語 {len(nvl)} / 近接ペア {pairs}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("codes", nargs="*", help="対象カテゴリのコード（省略で全部）")
    ap.add_argument("--cross", action="store_true", help="カテゴリをまたいだ重複・類似も調べる")
    ap.add_argument("--quiet", action="store_true", help="WARN の詳細を出さない")
    a = ap.parse_args()
    model_dir = Path(a.model_dir)
    rep = Report()
    chars = character_ids(model_dir)
    if not chars:
        rep.warn("CHARACTERS.md のキャスト一覧から id を読めない")
    codes = a.codes or sorted({p.code for p in PARTS}, key=lambda c: [p.code for p in PARTS].index(c))
    rows_by_part = {}
    for p in PARTS:
        if p.code in codes:
            rows_by_part[p.stem] = check_part(model_dir, p, rep, chars)
    for code in codes:
        check_category(code, [p for p in PARTS if p.code == code], rows_by_part, rep)
    # 重複（全体）
    seen: dict[str, str] = {}
    all_rows = [r for rs in rows_by_part.values() for r in rs]
    for r in all_rows:
        key = re.sub(r"[、。！？…]", "", strip_ruby(r.text))
        if key in seen:
            rep.err(f"重複: {seen[key]} と {r.id}: {r.text}")
        seen[key] = r.id
    if a.cross:
        grams = [(r.id, char_ngrams(r.text), r.text) for r in all_rows]
        for i in range(len(grams)):
            for j in range(i + 1, len(grams)):
                if grams[i][0].rsplit("_", 1)[0] == grams[j][0].rsplit("_", 1)[0]:
                    continue
                s = jaccard(grams[i][1], grams[j][1])
                if s >= 0.55:
                    rep.warn(f"カテゴリ間類似 {s:.2f} {grams[i][0]}「{grams[i][2]}」/ {grams[j][0]}「{grams[j][2]}」")
    for m in rep.infos:
        print("INFO ", m)
    if not a.quiet:
        for m in rep.warns:
            print("WARN ", m)
    for m in rep.errors:
        print("ERROR", m)
    print(f"--- ERROR {len(rep.errors)} / WARN {len(rep.warns)}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
