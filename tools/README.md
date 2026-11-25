# tools

コーパスの検証・並べ替えと、Style-Bert-VITS2（SBV2）用ファイルの生成に使うスクリプトです。
仕様は `CORPUS_PROMPT_JA.md` を参照してください。

| スクリプト | 用途 | 必要な環境 |
|---|---|---|
| `validate_corpus.py` | 3ファイルの整合性、文字数・記号・件数の目安、類似文などを検証する | 標準ライブラリのみ |
| `order_lines.py` | 下書き TSV を「先頭から録るほど効率がよい並び」に並べ、ID を振って3ファイルを書き出す | 標準ライブラリのみ（`--no-mora` のとき） |
| `draft_stats.py` | 下書き TSV の分布（文長・行末記号・話者など）を表示する | 標準ライブラリのみ |
| `coverage.py` | SBV2 と同じ読みで、モーラの出現数を数える | 下記の環境 |
| `sbv2_build.py` | `esd.list` / `esd.list.cleaned` / 収録用アクセントガイドを作る | 下記の環境 |
| `corpus_lib.py` `sbv2_text.py` `sbv2_esd.py` | 共通部品 | ― |

## SBV2 の読み推定を使う環境
SBV2 本体（PyPI の `style-bert-vits2`）の normalizer と g2p をそのまま呼びます。torch は不要です。
Python 3.11 で確認しています（3.13 では pyopenjtalk-dict のビルドが通りませんでした）。

```bash
python3.11 -m venv .venv
```
```bash
.venv/bin/pip install "numpy<2" pyopenjtalk-dict num2words loguru pydantic transformers sentencepiece
```
```bash
.venv/bin/pip install --no-deps style-bert-vits2==2.5.0
```

- `sbv2_text.py` は、torch を要求する `style_bert_vits2.nlp.bert_models` を差し替え、BERT のトークナイザ
  （`ku-nlp/deberta-v2-large-japanese-char-wwm`）だけを transformers で読み込みます。
  Hugging Face に接続できない場合は、1文字1トークンの代替トークナイザを使います（g2p はトークン数しか使わないため、結果は同じ）。
- 一致確認: 旧データの esd.list（887 行）をこの環境で処理すると、SBV2 が実際に出力した esd.list.cleaned と 887/887 行一致しました
  （本物のトークナイザでも、代替トークナイザでも同じ）。

## 作業の流れ
```bash
python tools/order_lines.py drafts/01_JOY.tsv 01_JOY Claude-Opus-5.5
```
```bash
python tools/validate_corpus.py Claude-Opus-5.5 --cross
```
```bash
.venv/bin/python tools/coverage.py Claude-Opus-5.5
```
```bash
.venv/bin/python tools/sbv2_build.py Claude-Opus-5.5 --review-dir review
```

- 本文を直したら、下書き TSV を直して `order_lines.py` からやり直します（ID の順番が変わることがあるため、
  `accent_overrides.tsv` の ID も確認する）。
- `validate_corpus.py` の `--cross` は、カテゴリをまたいだ類似文も調べます（ERROR は必ず直す。WARN は目安から外れたもの）。
- `sbv2_build.py` の `--review-dir` を付けると、カテゴリごとのレビュー用 TSV（ID、本文、esd テキスト、g2p のアクセント、修正後のアクセント）と、
  ルビの処理結果 `ruby_log.tsv` を書き出します。

## 下書き TSV の形式
UTF-8、タブ区切り。`#` で始まる行はコメントとして無視します。
```
character_style	nuance	intensity	nonverbal	near_pair_group	scene	text
```
- `near_pair_group` は近接ペアの記号（例: `P01`）。ペアでない行は `-`。
- `text` にはルビ付きの本文をそのまま書きます（例: `辛（ツラ）くて`）。

## sbv2_build.py が検査すること
- ルビ: 漢字のままでその位置がルビどおりに読めれば漢字を残し（BERT の意味情報を保つ）、読めなければルビのかなに置き換えます。
  かなにしても読めない場合、かなにすると直前のかなと結合して読みが変わる場合はエラーにします。
- 非言語（笑い・ため息など）: 行頭に置いたときと同じ音で読まれているか。読点の後で「は」「へ」が助詞と誤解析されるのを検出します。
- アクセント修正: `accent_overrides.tsv` のモーラ列が g2p の読みと完全に一致すること（読みは変えず、高低だけを変える）。
- 整合性: `len(phones)==len(tones)`、`sum(word2ph)==len(phones)`、`len(word2ph)==len(norm_text)+2`、全音素が SBV2 の記号集合に含まれること。
- `user_dict.csv`（OpenJTalk 形式）があれば、ビルド前に辞書として読み込みます。
