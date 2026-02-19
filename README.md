GPTを活用したコーパス用文章  
GPT-Corpuses13-2600

# 概要
下記モデルで作成した、日本語音声収録向けコーパス文章群です。
- Anthropic/Claude Sonnet 4.5
- Anthropic/Claude Opus 4.6 (High Effort)
- Google/Gemini 3 Pro
- OpenAI/ChatGPT 5.1 Thinking
- OpenAI/ChatGPT 5.3 Thinking（予定）

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

注意:
- すべてのファイルは"Shift-JIS(cp932)"エンコードで作成されています。
- 12_WHISPER内の文章および文章量は、モデルによって異なります。
- 既存データには `*_AUDIT.csv` が未同梱のものがあります。
- `CORPUS_PROMPT_JA.md` の最新仕様では `*_AUDIT.csv` の同時出力を推奨しています。

# 文章量
1カテゴリあたり200文です。
13カテゴリで1モデルあたり2,600文、モデル横断で合計7,800文です。

# 使用法
OREMOなどの録音ソフトに読み込むと収録しやすくなります。
1. [音名リストの読み込み]で IDs ファイルを選択
2. [コメントファイルの読み込み]で本文ファイルを選択
3. 必要に応じて監査CSVを別途参照して品質確認

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