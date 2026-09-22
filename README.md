GPTを活用したコーパス用文章  
GPT-Corpus13-2600

# 概要
下記モデルで作成した、日本語音声収録向けコーパス文章群です。
- Anthropic/Claude Sonnet 4.5
- Anthropic/Claude Opus 4.6 (High Effort)
- Google/Gemini 3 Pro
- Google/Gemini 3.1 Pro
- OpenAI/ChatGPT 5.1 Thinking
- OpenAI/ChatGPT 5.6 Sol(Ultra)

# ファイル構成
各モデルフォルダには、13カテゴリを格納しています。
- 01_JOY        喜び
- 02_ANGRY      怒り
- 03_SAD        悲しみ
- 04_FUN        楽しみ
- 05_SURPRISE   驚き
- 06_CONTEMPT   軽蔑
- 07_FEAR       恐怖
- 08_CONFUSE    混乱
- 09_NORMAL     中立
- 10_EXPLAIN    説明口調
- 11_ANNOUNCE   自動放送・案内
- 12_WHISPER    ささやき
- 13_LAZY       気だるげ

カテゴリごとに以下3種類のファイルが用意されています。
- 本文: `01_JOY.txt`（`[ID] [文章]`）
- IDs: `01_JOY_IDs.txt`（`[ID]` のみ）
- 監査CSV: `01_JOY_AUDIT.csv`（品質監査メタデータ。ない場合もある）

モデルフォルダ直下には、キャラクター設定と読み上げ方をまとめた `CHARACTERS.md` があります（新仕様で作成したモデルのみ）。

注意:
- 各モデルフォルダ内のファイルは"Shift-JIS(cp932)"エンコードで作成されています（`CHARACTERS.md` のみ UTF-8）。
- 12_WHISPER内の文章および文章量は、モデルによって異なります。
- 既存データには `*_AUDIT.csv` が未同梱のものがあります。
- `CORPUS_PROMPT_JA.md` の最新仕様では `*_AUDIT.csv` の同時出力を推奨しています。
- 最新仕様の `*_AUDIT.csv` は列構成が旧仕様と異なります（`scene` 列を追加し、`length_chars` `phoneme_tags` `reading_ease_score` を廃止）。

# 文章量
1カテゴリあたり200文です。
13カテゴリで1モデルあたり2,600文、モデル横断で合計7,800文です。

# 作成手順
AIに仕様ファイルを参照させて作成します。
1. `CHARACTERS_PROMPT_JA.md` を参照させ、モデルフォルダに `CHARACTERS.md` を作成
2. `CORPUS_PROMPT_JA.md` を参照させ、13カテゴリを1つずつ作成

# 使用法
OREMOなどの録音ソフトに読み込むと収録しやすくなります。
1. [音名リストの読み込み]で IDs ファイルを選択
2. [コメントファイルの読み込み]で本文ファイルを選択
3. 必要に応じて監査CSVを別途参照して品質確認
4. `CHARACTERS.md` で各キャラクターの読み方を確認（文ごとの話者は監査CSVの `character_style` で確認）

※ ソフトの詳細操作は各ツールのWiki等を参照してください。

# その他
趣味制作のため、カテゴリ内にキャラクター文体（例: 執事風）が含まれる場合があります。
[↑追記] キャラクター文体を積極的に含み、様々な用途に使用できるようプロンプトを再作成しました。
この変更は、既存モデル(Claude/Sonnet4.5, Google/Gemini3Pro, GPT-5.1-Thinking)には影響しません。

# 更新履歴
2026-02-19
- Claude-Opus-4.6のコーパスを再作成
- より多様なキャラクター文体を含むように変更
- たのしい。

2026-09-22
- コーパス作成プロンプトを編集
- 事前にキャラクターを作成し、概要をCHARACTERS.mdに記載するように変更
(この変更はGPT-6以降のコーパスから適応される予定です)