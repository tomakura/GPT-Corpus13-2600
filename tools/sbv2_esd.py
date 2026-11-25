"""コーパス本文 → SBV2 用テキストの変換と、音素・モーラ・アクセント表記のユーティリティ。

SBV2 の g2p（tools/sbv2_text.py 経由）を使うため、style-bert-vits2 と pyopenjtalk-dict が
入った環境で実行する（tools/README.md 参照）。
"""
from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sbv2_text  # noqa: E402
from corpus_lib import RUBY_RE  # noqa: E402
from style_bert_vits2.nlp.japanese.mora_list import MORA_KATA_TO_MORA_PHONEMES  # noqa: E402

PUNCT_PHONES = {"!", "?", "…", ",", ".", "'", "-"}
VOWELS = {"a", "i", "u", "e", "o"}

# 音素 (子音, 母音) → 代表のカタカナ（重複は一般的な表記を優先）
_PREFER = {("w", "a"): "ワ", ("y", "o"): "ヨ", ("y", "u"): "ユ", ("y", "a"): "ヤ", ("by", "o"): "ビョ",
           ("by", "u"): "ビュ", ("by", "a"): "ビャ", ("z", "u"): "ズ", ("j", "i"): "ジ", ("k", "e"): "ケ",
           (None, "o"): "オ", (None, "e"): "エ", (None, "u"): "ウ", (None, "i"): "イ", (None, "a"): "ア"}
PHONEMES_TO_KATA: dict[tuple, str] = {}
for _k, _v in MORA_KATA_TO_MORA_PHONEMES.items():
    PHONEMES_TO_KATA.setdefault(_v, _k)
PHONEMES_TO_KATA.update(_PREFER)
CONSONANTS = {c for c, _ in MORA_KATA_TO_MORA_PHONEMES.values() if c}

PUNCT_TO_JA = {",": "、", ".": "。", "!": "！", "?": "？", "…": "…", "'": "’", "-": "－"}
JA_TO_PUNCT = {v: k for k, v in PUNCT_TO_JA.items()}


def kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


@lru_cache(maxsize=None)
def clean(text: str):
    return sbv2_text.clean(text)


def phones_of(text: str) -> list[str]:
    return clean(text)[1]


def resolve_ruby(text: str) -> tuple[str, list[tuple[str, str, str]]]:
    """ルビ付き本文から SBV2 に渡すテキストを作る。

    各ルビについて、漢字のまま（ルビを外しただけ）の文と、その語をルビのひらがなに置き換えた文の
    音素列を比べる。一致すれば漢字を残し、食い違えばひらがなにする。
    戻り値: (esd 用テキスト, [(base, ruby, 採用した表記), ...])
    """
    spans = list(RUBY_RE.finditer(text))
    if not spans:
        return text, []
    pieces: list = []
    pos = 0
    for m in spans:
        pieces.append(text[pos : m.start()])
        pieces.append([m.group(1), kata_to_hira(m.group(2)), m.group(1)])  # base, kana, choice
        pos = m.end()
    pieces.append(text[pos:])

    def render() -> str:
        return "".join(p if isinstance(p, str) else p[2] for p in pieces)

    log = []
    for p in pieces:
        if isinstance(p, str):
            continue
        p[2] = p[0]
        a = phones_of(render())
        p[2] = p[1]
        b = phones_of(render())
        if a == b:
            p[2] = p[0]
        log.append((p[0], p[1], p[2]))
    return render(), log


def phones_to_moras(phones: list[str]) -> list[tuple[str, list[int]]]:
    """phones（先頭末尾の `_` 込み）を、(表示用トークン, そのトークンが占める phone の添字) の列にする。

    トークンはカタカナ1モーラ、`ー`（直前と同じ母音・撥音の長音）、または句読点。
    """
    out: list[tuple[str, list[int]]] = []
    i = 0
    prev_vowel = None
    n = len(phones)
    while i < n:
        p = phones[i]
        if p == "_":
            i += 1
            prev_vowel = None
            continue
        if p in PUNCT_PHONES:
            out.append((PUNCT_TO_JA[p], [i]))
            prev_vowel = None
            i += 1
            continue
        if p in VOWELS or p == "N":
            if prev_vowel == p:
                out.append(("ー", [i]))
            else:
                out.append((PHONEMES_TO_KATA[(None, p)], [i]))
            prev_vowel = p
            i += 1
            continue
        if p == "q":
            out.append(("ッ", [i]))
            prev_vowel = None
            i += 1
            continue
        if p in CONSONANTS and i + 1 < n and phones[i + 1] in VOWELS:
            out.append((PHONEMES_TO_KATA[(p, phones[i + 1])], [i, i + 1]))
            prev_vowel = phones[i + 1]
            i += 2
            continue
        raise ValueError(f"モーラに分けられない音素列: {phones[i:i+3]} in {' '.join(phones)}")
    return out


def moras_of(text: str) -> list[str]:
    return [m for m, _ in phones_to_moras(phones_of(text)) if m not in PUNCT_TO_JA.values()]


def accent_string(phones: list[str], tones: list[int]) -> str:
    """phones/tones を ↑↓ 付きカタカナにする。

    各句読点の後と行頭は低（0）から始まる。高くなる位置に ↑、下がる位置に ↓ を置く。
    """
    out = []
    level = 0
    for tok, idx in phones_to_moras(phones):
        if tok in PUNCT_TO_JA.values():
            out.append(tok)
            level = 0
            continue
        t = tones[idx[0]]
        if any(tones[j] != t for j in idx):
            raise ValueError("1モーラ内でアクセントが食い違う")
        if t != level:
            out.append("↑" if t == 1 else "↓")
            level = t
        out.append(tok)
    return "".join(out)


_TOKEN_RE = re.compile(r"[↑↓]|[ァ-ヴ][ァィゥェォャュョヮ]?|ー|[、。！？…’－]")


def parse_accent_string(s: str, phones: list[str]) -> list[int]:
    """↑↓ 付きカタカナを、phones と同じ長さの tones に変換する。

    文字列のモーラ列が phones から作ったモーラ列と一致しなければ ValueError。
    """
    s = s.replace(" ", "").replace("　", "")
    toks = _TOKEN_RE.findall(s)
    if "".join(toks) != s:
        raise ValueError(f"解釈できない文字がある: {s}")
    ref = phones_to_moras(phones)
    ref_toks = [t for t, _ in ref]
    seq = []
    level = 0
    for t in toks:
        if t == "↑":
            level = 1
        elif t == "↓":
            level = 0
        else:
            if t in PUNCT_TO_JA.values():
                seq.append((t, 0))
                level = 0
            else:
                seq.append((t, level))
    got = [t for t, _ in seq]
    if got != ref_toks:
        raise ValueError(f"モーラ列が一致しない:\n  override: {''.join(got)}\n  g2p     : {''.join(ref_toks)}")
    tones = [0] * len(phones)
    for (tok, lv), (_, idx) in zip(seq, ref):
        for j in idx:
            tones[j] = 0 if tok in PUNCT_TO_JA.values() else lv
    return tones
