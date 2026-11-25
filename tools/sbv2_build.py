"""コーパスから Style-Bert-VITS2 用の esd.list / esd.list.cleaned / 収録用アクセントガイドを作る。

使い方:
    python tools/sbv2_build.py Claude-Opus-5.5 [--speaker SPEAKER_NAME] [--review-dir DIR]

出力（<model_dir>/sbv2/）:
    esd.list             … `01_JOY\\JOY_001.wav|SPEAKER_NAME|JP|テキスト`（UTF-8, CRLF）
    esd.list.cleaned     … SBV2 の前処理と同じ形式。アクセントは accent_overrides.tsv で修正済み
    accent_guide/*.txt   … `ID ↑↓付きカタカナ`（CP932, CRLF）。OREMO のコメントファイルとして読める

入力:
    <model_dir>/*.txt（本文）、<model_dir>/sbv2/accent_overrides.tsv（任意）、<model_dir>/sbv2/user_dict.csv（任意）
    user_dict.csv は SBV2 の dict_data/default.csv と同じ OpenJTalk 形式。語単位で読み・アクセントを直す。
    accent_overrides.tsv は `ID<TAB>↑↓付きカタカナ` の行。`#` 以降はコメント。
    カタカナのモーラ列が SBV2 の読みと一致しない行はエラーにする（読みは変えず、アクセントだけを直すため）。

--review-dir を付けると、レビュー用の TSV（ID、本文、esd テキスト、g2p のアクセント、最終アクセント）と
ルビの処理結果を書き出す。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sbv2_esd  # noqa: E402
from corpus_lib import PARTS, load_part  # noqa: E402
from style_bert_vits2.nlp.symbols import SYMBOLS  # noqa: E402


def load_overrides(path: Path) -> dict[str, str]:
    ov: dict[str, str] = {}
    if not path.exists():
        return ov
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) < 2:
            raise ValueError(f"{path}:{n}: `ID<TAB>アクセント` の形式ではない: {line}")
        if cols[0] in ov:
            raise ValueError(f"{path}:{n}: ID が重複: {cols[0]}")
        ov[cols[0]] = cols[1].strip()
    return ov


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("--speaker", default="SPEAKER_NAME")
    ap.add_argument("--review-dir")
    a = ap.parse_args()
    md = Path(a.model_dir)
    out = md / "sbv2"
    (out / "accent_guide").mkdir(parents=True, exist_ok=True)
    user_dict = out / "user_dict.csv"
    if user_dict.exists():
        sbv2_esd.sbv2_text.load_user_dict(user_dict)
        print(f"ユーザー辞書を読み込んだ: {user_dict}")
    overrides = load_overrides(out / "accent_overrides.tsv")
    used_ov = set()
    errors: list[str] = []
    esd_lines, cleaned_lines = [], []
    review: dict[str, list[str]] = {}
    ruby_log = []
    symbols = set(SYMBOLS)
    n_lines = 0
    for p in PARTS:
        if not (md / f"{p.stem}.txt").exists():
            continue
        rows = load_part(md, p)
        guide = []
        rv = review.setdefault(p.stem, [])
        for r in rows:
            n_lines += 1
            esd_text, log = sbv2_esd.resolve_ruby(r.text)
            for base, kana, choice in log:
                ruby_log.append(f"{r.id}\t{base}\t{kana}\t{'かな' if choice == kana else '漢字のまま'}\t{esd_text}")
            if "（" in esd_text or "）" in esd_text:
                errors.append(f"{r.id}: esd テキストにカッコが残っている: {esd_text}")
            try:
                norm, phones, tones, w2p = sbv2_esd.sbv2_text.clean(esd_text, raise_yomi_error=True)
            except Exception as e:
                errors.append(f"{r.id}: SBV2 の読みでエラー: {e}")
                continue
            g2p_acc = sbv2_esd.accent_string(phones, tones)
            if r.id in overrides:
                used_ov.add(r.id)
                try:
                    tones = sbv2_esd.parse_accent_string(overrides[r.id], phones)
                except ValueError as e:
                    errors.append(f"{r.id}: accent_overrides の行が読みと一致しない: {e}")
            final_acc = sbv2_esd.accent_string(phones, tones)
            # 整合性
            if len(phones) != len(tones):
                errors.append(f"{r.id}: phones と tones の長さが違う")
            if sum(w2p) != len(phones):
                errors.append(f"{r.id}: sum(word2ph) != len(phones)")
            if len(w2p) != len(norm) + 2:
                errors.append(f"{r.id}: len(word2ph) != len(norm_text)+2")
            bad = [x for x in phones if x not in symbols]
            if bad:
                errors.append(f"{r.id}: SBV2 の記号集合にない音素 {bad}")
            wav = f"{p.stem}\\{r.id}.wav"
            esd_lines.append(f"{wav}|{a.speaker}|JP|{esd_text}")
            cleaned_lines.append(
                f"Data\\{a.speaker}\\wavs\\{wav}|{a.speaker}|JP|{norm}|{' '.join(phones)}|{' '.join(map(str, tones))}|{' '.join(map(str, w2p))}"
            )
            guide.append(f"{r.id} {final_acc}")
            rv.append("\t".join([r.id, r.text, esd_text, g2p_acc, final_acc if final_acc != g2p_acc else ""]))
        (out / "accent_guide" / f"{p.stem}.txt").write_bytes(("\r\n".join(guide) + "\r\n").encode("cp932"))
    unused = sorted(set(overrides) - used_ov)
    for u in unused:
        errors.append(f"accent_overrides の ID がコーパスにない: {u}")
    (out / "esd.list").write_bytes(("\r\n".join(esd_lines) + "\r\n").encode("utf-8"))
    (out / "esd.list.cleaned").write_bytes(("\r\n".join(cleaned_lines) + "\r\n").encode("utf-8"))
    if a.review_dir:
        rd = Path(a.review_dir)
        rd.mkdir(parents=True, exist_ok=True)
        for stem, lines in review.items():
            (rd / f"{stem}.tsv").write_text("ID\t本文\tesd\tg2p\toverride\n" + "\n".join(lines) + "\n", encoding="utf-8")
        (rd / "ruby_log.tsv").write_text("ID\tbase\tkana\t採用\tesd\n" + "\n".join(ruby_log) + "\n", encoding="utf-8")
    n_sub = sum(1 for l in ruby_log if "\tかな\t" in l)
    print(f"{n_lines} 行 / ルビ {len(ruby_log)} 件（かなに置換 {n_sub}）/ アクセント修正 {len(used_ov)} 行")
    for e in errors:
        print("ERROR", e)
    print(f"--- ERROR {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
