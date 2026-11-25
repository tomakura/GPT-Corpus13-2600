"""Style-Bert-VITS2 のテキスト前処理（normalize_text + g2p）を torch なしで呼ぶための薄いラッパ。

SBV2 本体（PyPI: style-bert-vits2）の normalizer / g2p をそのまま使う。
g2p が word2ph の計算に使う BERT トークナイザ（ku-nlp/deberta-v2-large-japanese-char-wwm）だけを
transformers から直接ロードし、torch を要求する bert_models モジュールを差し替える。
"""
from __future__ import annotations

import sys
import types

_TOKENIZER_NAME = "ku-nlp/deberta-v2-large-japanese-char-wwm"
_tok = None


class _CharTokenizer:
    """文字単位トークナイザ（ku-nlp/deberta-v2-large-japanese-char-wwm 相当）。

    Hugging Face に接続できない環境向けの代替。g2p は word2ph の計算で
    tokenize() の長さだけを使うので、1文字1トークンで同じ結果になる。
    旧 esd.list.cleaned との突き合わせで一致を確認済み（tools/README.md 参照）。
    """

    def tokenize(self, text: str) -> list[str]:
        return list(text)


def _load_tokenizer(language=None, pretrained_model_name_or_path=None, *a, **k):
    global _tok
    if _tok is None:
        from transformers import AutoTokenizer

        name = pretrained_model_name_or_path or _TOKENIZER_NAME
        try:  # キャッシュ済みなら通信しない
            _tok = AutoTokenizer.from_pretrained(name, local_files_only=True)
        except Exception:
            try:
                _tok = AutoTokenizer.from_pretrained(name)
            except Exception:
                _tok = _CharTokenizer()
    return _tok


_stub = types.ModuleType("style_bert_vits2.nlp.bert_models")
_stub.load_tokenizer = _load_tokenizer
sys.modules["style_bert_vits2.nlp.bert_models"] = _stub
import style_bert_vits2.nlp as _nlp  # noqa: E402

_nlp.bert_models = _stub

from style_bert_vits2.nlp.japanese.g2p import g2p  # noqa: E402
from style_bert_vits2.nlp.japanese.normalizer import normalize_text  # noqa: E402


def clean(text: str, use_jp_extra: bool = True, raise_yomi_error: bool = True):
    """SBV2 の clean_text(JP) と同じ (norm_text, phones, tones, word2ph) を返す。"""
    norm_text = normalize_text(text)
    phones, tones, word2ph = g2p(norm_text, use_jp_extra=use_jp_extra, raise_yomi_error=raise_yomi_error)
    return norm_text, phones, tones, word2ph
