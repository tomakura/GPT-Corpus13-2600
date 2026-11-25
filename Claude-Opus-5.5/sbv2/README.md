# Style-Bert-VITS2 用ファイル（Claude-Opus-5.5）

台本をそのまま正解テキストにした `esd.list` と、読み・アクセントを確認したうえで作った `esd.list.cleaned` です。
Whisper の書き起こしを使わないので、認識ミス（例:「信頼を」→「戦来を」）や句点の欠落が入りません。
読みの誤り（例:「辛くて」→ カラクテ）は台本のルビで、アクセントの誤りは `accent_overrides.tsv` で直してあります。

対象は **JP-Extra** のモデルです（cleaned の音素は JP-Extra の記号集合で作っています）。

## ファイル
| ファイル | 内容 |
|---|---|
| `esd.list` | `01_JOY\JOY_001.wav\|SPEAKER_NAME\|JP\|テキスト`（UTF-8, CRLF）。2,800 行 |
| `esd.list.cleaned` | SBV2 の前処理と同じ形式（`wav\|話者\|JP\|norm_text\|phones\|tones\|word2ph`）。アクセント修正済み |
| `apply_cleaned.py` | 前処理で作られた `train.list` / `val.list` を、この cleaned の内容に差し替える（標準ライブラリのみ） |
| `user_dict.csv` | 架空の地名など、辞書に足した語（SBV2 の `dict_data/default.csv` と同じ形式） |
| `accent_guide/*.txt` | 収録用アクセントガイド（CP932, CRLF）。`ID ↑↓付きカタカナ` |
| `accent_overrides.tsv` | アクセント修正の元データ（`ID<TAB>行全体の↑↓付きカタカナ  # 理由`） |
| `accent_uncertain.tsv` | アクセントに確信が持てない箇所の一覧。収録時に耳で確認してほしいところ |

## 1. 話者名を置き換える
`SPEAKER_NAME` を、学習に使う話者名に置き換えます（2つのファイルの両方）。

Linux / macOS / WSL:
```bash
sed -i 's/SPEAKER_NAME/MyVoice/g' esd.list esd.list.cleaned
```

Windows（PowerShell）:
```powershell
foreach ($f in "esd.list","esd.list.cleaned") { (Get-Content $f -Raw -Encoding UTF8) -replace "SPEAKER_NAME","MyVoice" | Set-Content $f -NoNewline -Encoding UTF8 }
```
PowerShell 5.1 の `-Encoding UTF8` は BOM を付けます。BOM が気になる場合はエディタで UTF-8（BOM なし）で保存し直してください。

## 2. 収録と配置
1. 台本どおりに録音し、`01_JOY\JOY_001.wav` のように **カテゴリのフォルダ＋ID のファイル名** で保存します。
2. SBV2 の `Data\<モデル名>\raw\` に、フォルダごと置きます。
3. `esd.list` を `Data\<モデル名>\esd.list` に置きます。録っていない行や使わない行は、`esd.list` から消しておきます。
4. 台本と違う読み方をした行（言い間違い、笑い方を大きく変えたなど）は、録り直すか `esd.list` から消します。
   テキストと音声がずれた行は、学習を悪くします。

## 3. 前処理と差し替え
1. SBV2 の前処理を実行します（WebUI の「データセット作成・前処理」、または `preprocess_all.py`）。
   この段階で SBV2 が `esd.list.cleaned` と `train.list` / `val.list` を作ります（自前の cleaned は上書きされます）。
2. SBV2 のフォルダで `apply_cleaned.py` を実行し、`train.list` / `val.list` の読み・アクセントを差し替えます。
   ```bash
   python path/to/apply_cleaned.py --cleaned path/to/esd.list.cleaned --lists Data/<モデル名>/train.list Data/<モデル名>/val.list --dry-run
   ```
   集計を確認したら `--dry-run` を外して実行します。元のファイルは `train.list.bak-日時` として残ります。
   - 行の対応は wav のファイル名で取ります（`01_JOY/JOY_001` → 見つからなければ `JOY_001`）。
   - 話者名・wav のパス・言語は SBV2 が書いたものを残し、4〜7列目だけを置き換えます。
3. テキストか word2ph が変わった行は、BERT 特徴量を作り直します。
   SBV2 の bert_gen は、音素の数が同じなら既存の `.bert.pt` を使い回すため、先に削除します。
   - `apply_cleaned.py` に `--remove-stale-bert` を付けると、該当する `.bert.pt` を削除します（一覧は `stale_bert.txt`）。
   - 削除した後、BERT 特徴量の生成（`bert_gen.py`、または WebUI の前処理）をもう一度実行します。
   - スタイルベクトル（style_gen）は音声から作るので、作り直す必要はありません。
4. いつもどおり学習します。

## 4. ユーザー辞書（推論時）
`user_dict.csv` の語（架空の地名など）は、cleaned には反映済みです。
学習したモデルで同じ語を読み上げるときのために、SBV2 の `dict_data/default.csv` に行を追加してください（`#` で始まる行は説明なので不要）。
文脈ID 1348・コスト -988 は、SBV2 のユーザー辞書で「固有名詞・優先度10」にあたる値です。

## 5. 収録用アクセントガイド
`accent_guide/*.txt` は、本文ファイルと同じく `ID 内容` の形なので、OREMO の「コメントファイルの読み込み」で読めます。
- `↑` はそのモーラから高く、`↓` はそのモーラから低く読む印です。句読点の後と行頭は低から始まります。
- `ー` は長音のほか、同じ母音が続く箇所（「とおる」の「お」など）も表します。
- 学習ラベル（cleaned の tones）はこのガイドと同じです。ガイドから大きく外れたイントネーションで読むと、ラベルと音声がずれます。
- 感情表現のための抑揚の誇張は問題ありません。ずれて困るのは、アクセント核の位置（どこで下がるか）です。

## 6. 修正して作り直す
読みやアクセントを直したいときは、リポジトリのルートで次を実行します（環境構築は `tools/README.md`）。
- 読みを直す: 本文ファイルの該当語にルビを振る（例: `辛（ツラ）くて`）。
- アクセントを直す: `accent_overrides.tsv` に `ID<TAB>行全体の↑↓付きカタカナ` を書く。カタカナのモーラ列は、レビュー出力の g2p 列と完全に一致させます（読みは変えず、高低だけを変えるため）。
```bash
python tools/sbv2_build.py Claude-Opus-5.5 --review-dir review
```

## 確認したこと・していないこと
- 確認済み: 全 2,800 行で `len(phones)==len(tones)`、`sum(word2ph)==len(phones)`、`len(word2ph)==len(norm_text)+2`、全音素が SBV2 の記号集合に含まれること。
  旧 esd.list（887 行）を同じパイプラインに通すと、添付の旧 cleaned と 887/887 行一致すること（style-bert-vits2 2.5.0 の g2p）。
  ルビの語がルビどおりに読まれていること、非言語の表記が表記どおりに読まれていることは、ビルド時に機械的に検査しています。
- 目視による判断: 読みのレビュー（語の一覧と多読語の確認）とアクセントのレビュー（ANNOUNCE は全行、それ以外は誤りが出やすい箇所を中心に）。
  アクセントは標準語（東京方言）の辞書的なアクセントを基準にしていますが、保証はできません。迷った箇所は `accent_uncertain.tsv` にあります。
