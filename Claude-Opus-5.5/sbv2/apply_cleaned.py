"""Style-Bert-VITS2 の train.list / val.list の読み・アクセントを、このフォルダの esd.list.cleaned に差し替える。

SBV2 の前処理（preprocess_text）は esd.list.cleaned を毎回作り直すので、検証済みの cleaned を
そのまま置いても上書きされる。そこで前処理が終わった後に、train.list / val.list の
norm_text・phones・tones・word2ph（4〜7列目）だけを、この cleaned の値に置き換える。
wav のパス・話者名・言語（1〜3列目）は SBV2 が書いたものをそのまま残す。

標準ライブラリだけで動く。SBV2 のフォルダで実行する例:

    python apply_cleaned.py --cleaned path/to/esd.list.cleaned ^
        --lists Data/モデル名/train.list Data/モデル名/val.list

- 行の対応は wav ファイル名で取る（既定は「親フォルダ名/ファイル名」、見つからなければファイル名だけ）。
- 元のファイルは `train.list.bak-日時` のように残す。`--dry-run` を付けると何も書き換えない。
- norm_text か word2ph が変わった行は、BERT 特徴量（*.bert.pt）を作り直す必要がある。
  SBV2 の bert_gen は、音素の数が同じなら既存の .bert.pt を使い回すため、
  該当する .bert.pt の一覧を `stale_bert.txt` に記録する。`--remove-stale-bert` を付けると、
  その .bert.pt を削除する（その後 bert_gen を実行すると作り直される）。
- 書き換えは、全リストの検査が通ってから行う。`stale_bert.txt` はリストより先に書き、
  削除できた分だけ記録から外すので、途中で失敗しても再実行すれば続きから処理できる。
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import sys
from pathlib import Path, PureWindowsPath


def split_path(p: str) -> tuple[str, str]:
    """wav のパスから (親フォルダ名, 拡張子なしのファイル名) を小文字で返す。区切りは / と \\ の両方を扱う。"""
    parts = PureWindowsPath(p.replace("/", "\\")).parts
    name = parts[-1] if parts else p
    parent = parts[-2] if len(parts) >= 2 else ""
    stem = name.rsplit(".", 1)[0]
    return parent.lower(), stem.lower()


def check_fields(f: list[str], where: str) -> None:
    if len(f) != 7:
        raise ValueError(f"{where}: 列の数が 7 ではない（{len(f)}）")
    phones, tones, w2p = f[4].split(), f[5].split(), f[6].split()
    if len(phones) != len(tones):
        raise ValueError(f"{where}: phones と tones の数が違う")
    if sum(int(x) for x in w2p) != len(phones):
        raise ValueError(f"{where}: word2ph の合計が phones の数と違う")


def load_cleaned(path: Path) -> tuple[dict, dict]:
    by_pair: dict[tuple[str, str], list[str]] = {}
    by_stem: dict[str, list[list[str]]] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        f = line.split("|")
        check_fields(f, f"{path}:{n}")
        key = split_path(f[0])
        if key in by_pair:
            raise ValueError(f"{path}:{n}: wav が重複している: {f[0]}")
        by_pair[key] = f
        by_stem.setdefault(key[1], []).append(f)
    return by_pair, by_stem


def bert_path(wav: str) -> str:
    """wav に対応する BERT 特徴量のパス（SBV2 の bert_gen と同じく、拡張子 .wav を .bert.pt にする）。

    拡張子は大文字小文字を区別しない。.wav で終わらないパスには空文字を返す（削除の対象にしない）。
    """
    if not re.search(r"\.wav$", wav, flags=re.IGNORECASE):
        return ""
    return re.sub(r"\.wav$", ".bert.pt", wav, flags=re.IGNORECASE)


STALE_FILE = Path("stale_bert.txt")


def read_stale() -> list[str]:
    """前回までに記録した、作り直しが済んでいない .bert.pt の一覧。"""
    if not STALE_FILE.exists():
        return []
    return [l.strip() for l in STALE_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_stale(paths: list[str]) -> None:
    if paths:
        STALE_FILE.write_text("\n".join(paths) + "\n", encoding="utf-8")
    elif STALE_FILE.exists():
        STALE_FILE.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cleaned", required=True, help="このフォルダの esd.list.cleaned")
    ap.add_argument("--lists", nargs="+", required=True, help="SBV2 が作った train.list / val.list")
    ap.add_argument("--match", choices=["auto", "stem"], default="auto",
                    help="auto: 親フォルダ名/ファイル名で対応を取り、なければファイル名だけ。stem: ファイル名だけ")
    ap.add_argument("--dry-run", action="store_true", help="集計だけして、ファイルは書き換えない")
    ap.add_argument("--remove-stale-bert", action="store_true", help="作り直しが必要な .bert.pt を削除する")
    a = ap.parse_args()

    by_pair, by_stem = load_cleaned(Path(a.cleaned))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    new_stale: list[str] = []
    used: set[tuple[str, str]] = set()
    total = {"lines": 0, "replaced": 0, "unmatched": 0, "phones": 0, "tones": 0, "text": 0}

    # 1段階目: すべてのリストを読み、検査し、変換をメモリ上で済ませる（ここで失敗したら何も書かない）
    outputs: list[tuple[Path, bytes]] = []
    for lp in map(Path, a.lists):
        raw = lp.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        out_lines = []
        unmatched = []
        for n, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            total["lines"] += 1
            f = line.split("|")
            if len(f) != 7:
                raise ValueError(f"{lp}:{n}: 列の数が 7 ではない（{len(f)}）")
            key = split_path(f[0])
            ours = None
            if a.match == "auto" and key in by_pair:
                ours = by_pair[key]
            elif len(by_stem.get(key[1], [])) == 1:
                ours = by_stem[key[1]][0]
            if ours is None:
                unmatched.append(f[0])
                total["unmatched"] += 1
                out_lines.append(line)
                continue
            used.add(split_path(ours[0]))
            total["replaced"] += 1
            if f[4] != ours[4]:
                total["phones"] += 1
            if f[5] != ours[5]:
                total["tones"] += 1
            if f[3] != ours[3] or f[6] != ours[6]:
                total["text"] += 1
                b = bert_path(f[0])
                if b:
                    new_stale.append(b)
            out_lines.append("|".join(f[:3] + ours[3:]))
        print(f"{lp}: {len(out_lines)} 行（対応なし {len(unmatched)} 行）")
        for u in unmatched[:10]:
            print(f"  対応なし: {u}")
        if len(unmatched) > 10:
            print(f"  …ほか {len(unmatched) - 10} 行")
        outputs.append((lp, (nl.join(out_lines) + nl).encode("utf-8")))

    print(f"差し替え {total['replaced']} / {total['lines']} 行"
          f"（音素が変わった {total['phones']}、アクセントが変わった {total['tones']}、"
          f"テキストか word2ph が変わった {total['text']}）")
    print(f"cleaned のうち train/val に無かった行: {len(by_pair) - len(used)}（未収録の wav や、学習から外した行）")

    # 前回の実行で作り直しが済んでいない分も合わせる（途中で失敗した後の再実行で取りこぼさないため）
    stale = list(dict.fromkeys(read_stale() + new_stale))
    if a.dry_run:
        if stale:
            print(f"BERT 特徴量の作り直しが必要な行: {len(stale)}（前回までの未処理分を含む）")
        return 0

    # 2段階目: 作り直しの記録を先に書き、それからリストを書き換える
    write_stale(stale)
    for lp, data in outputs:
        bak = lp.with_name(f"{lp.name}.bak-{stamp}")
        shutil.copy2(lp, bak)
        lp.write_bytes(data)
        print(f"{lp}: 書き換えた（元のファイル: {bak.name}）")

    if stale:
        print(f"BERT 特徴量の作り直しが必要な {len(stale)} 行を {STALE_FILE} に記録した。")
        if a.remove_stale_bert:
            removed, remaining = 0, []
            for b in stale:
                if not b.lower().endswith(".bert.pt"):
                    remaining.append(b)
                    print(f"  .bert.pt ではないので削除しない: {b}", file=sys.stderr)
                    continue
                try:
                    if os.path.exists(b):
                        os.remove(b)
                        removed += 1
                except OSError as e:
                    remaining.append(b)
                    print(f"  削除できなかった: {b}（{e}）", file=sys.stderr)
            write_stale(remaining)
            print(f"  .bert.pt を {removed} 個削除した。続けて bert_gen を実行すること。")
            if remaining:
                print(f"  削除できなかった {len(remaining)} 行は {STALE_FILE} に残した。原因を直して再実行すること。")
        else:
            print("  bert_gen の前に、これらの .bert.pt を削除する（--remove-stale-bert でも消せる）。")
    print("次の手順: bert_gen（BERT 特徴量）→ 学習。style_gen は音声から作るので作り直し不要。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
