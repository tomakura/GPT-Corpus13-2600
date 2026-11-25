"""コーパス仕様 v3 の共通定義とテキスト処理（標準ライブラリのみ）。"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# カテゴリ定義
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Part:
    no: str
    code: str
    sub: str | None
    count: int

    @property
    def stem(self) -> str:
        return f"{self.no}_{self.code}" + (f"_{self.sub}" if self.sub else "")

    @property
    def prefix(self) -> str:
        return self.code + (f"_{self.sub}" if self.sub else "")

    @property
    def category_total(self) -> int:
        return 300 if self.code in ("WHISPER", "LAZY") else 200


PARTS: list[Part] = [
    Part("01", "JOY", None, 200),
    Part("02", "ANGRY", None, 200),
    Part("03", "SAD", None, 200),
    Part("04", "FUN", None, 200),
    Part("05", "SURPRISE", None, 200),
    Part("06", "CONTEMPT", None, 200),
    Part("07", "FEAR", None, 200),
    Part("08", "CONFUSE", None, 200),
    Part("09", "NORMAL", None, 200),
    Part("10", "EXPLAIN", None, 200),
    Part("11", "ANNOUNCE", None, 200),
    Part("12", "WHISPER", "NORMAL", 60),
    Part("12", "WHISPER", "JOY", 40),
    Part("12", "WHISPER", "FUN", 40),
    Part("12", "WHISPER", "SAD", 40),
    Part("12", "WHISPER", "ANGRY", 40),
    Part("12", "WHISPER", "FEAR", 40),
    Part("12", "WHISPER", "CONTEMPT", 40),
    Part("13", "LAZY", "NORMAL", 75),
    Part("13", "LAZY", "ANGRY", 45),
    Part("13", "LAZY", "SAD", 45),
    Part("13", "LAZY", "JOY", 45),
    Part("13", "LAZY", "FUN", 45),
    Part("13", "LAZY", "CONTEMPT", 45),
]
PART_BY_STEM = {p.stem: p for p in PARTS}
PART_BY_PREFIX = {p.prefix: p for p in PARTS}

EMOTIONAL = {"JOY", "ANGRY", "SAD", "FUN", "SURPRISE", "CONTEMPT", "FEAR", "CONFUSE"}
CHAR_RATIO_CODES = EMOTIONAL | {"WHISPER", "LAZY"}

CSV_HEADER = ["id", "character_style", "nuance", "intensity", "punctuation", "nonverbal", "near_pair_group", "scene"]
INTENSITIES = {"weak", "mid", "strong"}
NONVERBAL_TYPES = {"none", "laugh", "sigh", "gasp", "sob", "yawn"}
PUNCTS = ["。", "！", "？", "…", "？！"]

# 行末記号の目安（200 文あたり）: (min, max)
_P_GENERAL = {"。": (110, 160), "！": (10, 45), "？": (8, 35), "…": (6, 24), "？！": (0, 12)}


def punct_targets(code: str) -> dict[str, tuple[int, int]]:
    if code == "EXPLAIN":
        return {"。": (140, 185), "！": (3, 25), "？": (5, 30), "…": (0, 8), "？！": (0, 3)}
    if code == "ANNOUNCE":
        return {"。": (185, 200), "！": (0, 8), "？": (0, 8), "…": (0, 0), "？！": (0, 0)}
    if code == "LAZY":
        return {"。": (120, 170), "！": (0, 15), "？": (8, 35), "…": (15, 45), "？！": (0, 5)}
    t = dict(_P_GENERAL)
    if code in ("ANGRY", "SURPRISE", "JOY", "FUN"):
        t["！"] = (10, 60)
    if code in ("SURPRISE", "ANGRY", "CONFUSE"):
        t["？！"] = (0, 20)
    return t


def nonverbal_target(code: str) -> tuple[int, int]:
    """行数の目安（カテゴリ全体）。"""
    if code in EMOTIONAL:
        return (10, 20)
    if code in ("WHISPER", "LAZY"):
        return (15, 30)
    if code == "NORMAL":
        return (4, 10)
    if code == "EXPLAIN":
        return (0, 4)
    return (0, 0)


def length_limits(code: str) -> tuple[int, int]:
    return (10, 80) if code == "ANNOUNCE" else (6, 60)


def length_band(code: str, n: int) -> str:
    if code == "ANNOUNCE":
        return "S" if n <= 24 else ("M" if n <= 49 else "L")
    return "S" if n <= 17 else ("M" if n <= 35 else "L")


BAND_TARGETS = {"S": (40, 60), "M": (80, 100), "L": (50, 70)}  # 200 文あたり

# ---------------------------------------------------------------------------
# テキスト処理
# ---------------------------------------------------------------------------

RUBY_RE = re.compile(r"([0-9一-鿿々]+)（([ァ-ヺー]+)）")
ANY_PAREN_RE = re.compile(r"[（）()]")
ALLOWED_RE = re.compile(r"^[ぁ-ゖゝゞァ-ヺー一-鿿々0-9、。！？…（）]+$")
SENT_END_RE = re.compile(r"(？！|[。！？…])")

NONVERBAL_TOKENS = {
    "laugh": ["うふふ", "ふふっ", "ふふ", "くすっ", "くすくす", "あははっ", "あはは", "ハハハッ", "ははっ", "えへへ", "へへへっ", "へへ", "くくっ", "ふっ", "はっ"],
    "sigh": ["はぁ…", "はあ", "ふう"],
    "gasp": ["ひっ"],
    "sob": ["うぅ…", "ぐすっ"],
    "yawn": ["ふわぁ…", "ふぁ…"],
}

CLICHES = ["胸が", "心まで", "そっと", "静かに", "ゆっくり", "一緒に", "本当に"]
EMOTION_WORDS = ["うれし", "嬉し", "悲し", "かなし", "怖", "こわ", "幸せ", "しあわせ", "楽し", "たのし", "寂し", "さびし", "さみし", "腹が立", "むかつ", "不安", "びっくり", "驚"]


def strip_ruby(text: str) -> str:
    return RUBY_RE.sub(r"\1", text)


def text_len(text: str) -> int:
    return len(strip_ruby(text))


def final_punct(text: str) -> str:
    if text.endswith("？！"):
        return "？！"
    return text[-1] if text and text[-1] in "。！？…" else ""


def sentences(text: str) -> list[str]:
    t = strip_ruby(text)
    parts = SENT_END_RE.split(t)
    out, buf = [], ""
    for p in parts:
        if not p:
            continue
        if SENT_END_RE.fullmatch(p):
            buf += p
            out.append(buf)
            buf = ""
        else:
            buf += p
    if buf:
        out.append(buf)
    # 末尾が記号だけの断片（例: 文末の「…」の後の「。」）は前の文に含める
    merged: list[str] = []
    for s in out:
        if merged and not re.search(r"[^\s。！？…、]", s):
            merged[-1] += s
        else:
            merged.append(s)
    return merged


def opener(text: str) -> str:
    t = strip_ruby(text)
    m = re.match(r"^([^、。！？…]{1,6})、", t)
    return m.group(1) + "、" if m else ""


def char_ngrams(text: str, n: int = 3) -> set[str]:
    t = re.sub(r"[、。！？…]", "", strip_ruby(text))
    return {t[i : i + n] for i in range(max(1, len(t) - n + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# 入出力
# ---------------------------------------------------------------------------


@dataclass
class Row:
    id: str
    text: str
    character_style: str = "none"
    nuance: str = ""
    intensity: str = "mid"
    punctuation: str = ""
    nonverbal: str = "none"
    near_pair_group: str = ""
    scene: str = ""
    extra: dict = field(default_factory=dict)


def read_cp932_lines(path: Path) -> tuple[list[str], bytes]:
    raw = path.read_bytes()
    text = raw.decode("cp932")
    return text.split("\r\n") if "\r\n" in text else text.splitlines(), raw


def load_part(model_dir: Path, part: Part) -> list[Row]:
    lines, _ = read_cp932_lines(model_dir / f"{part.stem}.txt")
    lines = [l for l in lines if l]
    rows = []
    for l in lines:
        i, t = l.split(" ", 1)
        rows.append(Row(id=i, text=t))
    csv_path = model_dir / f"{part.stem}_AUDIT.csv"
    if csv_path.exists():
        data = csv_path.read_bytes().decode("cp932")
        meta = {r["id"]: r for r in csv.DictReader(io.StringIO(data))}
        for r in rows:
            m = meta.get(r.id)
            if m:
                for k in CSV_HEADER[1:]:
                    setattr(r, k, m.get(k, ""))
    return rows


def write_part(model_dir: Path, part: Part, rows: list[Row]) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{r.id} {r.text}\r\n" for r in rows)
    ids = "".join(f"{r.id}\r\n" for r in rows)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(CSV_HEADER)
    for r in rows:
        w.writerow([r.id, r.character_style, r.nuance, r.intensity, final_punct(r.text), r.nonverbal, r.near_pair_group, r.scene])
    (model_dir / f"{part.stem}.txt").write_bytes(body.encode("cp932"))
    (model_dir / f"{part.stem}_IDs.txt").write_bytes(ids.encode("cp932"))
    (model_dir / f"{part.stem}_AUDIT.csv").write_bytes(buf.getvalue().encode("cp932"))


DRAFT_COLUMNS = ["character_style", "nuance", "intensity", "nonverbal", "near_pair_group", "scene", "text"]


def load_draft(path: Path) -> list[Row]:
    """下書き TSV（UTF-8）: character_style, nuance, intensity, nonverbal, near_pair_group, scene, text。

    `#` で始まる行と空行は無視する。near_pair_group は空欄可（`-` も空欄扱い）。
    """
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != len(DRAFT_COLUMNS):
            raise ValueError(f"{path}:{n}: 列数が {len(cols)}（{len(DRAFT_COLUMNS)} 必要）: {line}")
        d = dict(zip(DRAFT_COLUMNS, [c.strip() for c in cols]))
        if d["near_pair_group"] == "-":
            d["near_pair_group"] = ""
        rows.append(Row(id="", **d))
    return rows
