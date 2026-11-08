# Google Meet 議事録 自動作成ツール（プロトタイプ）

会議の録音ファイルから議事録を自動で作り、Google ドキュメントに保存します。

## 仕組み

```
録音ファイル（mp4 / m4a / mp3 など）
   │
   ▼  transcribe.py  … OpenAI Whisper API で「音声 → 文字」
文字起こしテキスト
   │
   ▼  summarize.py   … Claude API で「長い会話 → 議事録の形」
議事録テキスト
   │
   ▼  google_docs.py … Google Docs API で「新しいドキュメントを作って書き込む」
Google ドキュメント（URL が表示される）
```

全体の流れは `main.py` が管理しています。

| ファイル | 役割 |
|---|---|
| `main.py` | 全体の流れを管理する。ここを実行する |
| `transcribe.py` | 文字起こし（Whisper） |
| `summarize.py` | 要約（Claude）。議事録の形式を変えたいときは `SYSTEM_PROMPT` を編集する |
| `google_docs.py` | Google ドキュメントへの保存 |
| `sample_transcript.txt` | 動作確認用のサンプル会話 |
| `output/` | 文字起こしと議事録のコピーが自動で保存される |

---

## セットアップ（最初の1回だけ）

### 1. Python の仮想環境（準備済み）

このプロジェクト用のライブラリは `C:\Users\kt061\.venvs\meet-minutes` にインストールしてあります。
（フォルダのパスが長すぎて Windows の制限に引っかかるため、短い場所に作りました）

コマンドを実行するときは `python` の代わりに次のように書きます。

```powershell
C:\Users\kt061\.venvs\meet-minutes\Scripts\python main.py --help
```

作り直す場合：

```powershell
python -m venv C:\Users\kt061\.venvs\meet-minutes
C:\Users\kt061\.venvs\meet-minutes\Scripts\python -m pip install -r requirements.txt
```

### 2. API キーを用意する

API キーは「このサービスを使っていいのは自分です」と証明する合言葉です。料金も API キーごとにかかります。

1. OpenAI のキー：https://platform.openai.com/api-keys で発行（クレジットのチャージが必要）
2. Anthropic のキー：https://platform.claude.com/settings/keys で発行（クレジットのチャージが必要）
3. `.env.example` をコピーして `.env` という名前にし、2つのキーを書き込む

> `.env` は他人に見せないでください。`.gitignore` に入れてあるので、Git を使っても公開されません。

### 3. Google Cloud の設定（Google Docs API を使えるようにする）

Google の API を使うには、「どのアプリが」「誰の許可を得て」アクセスするかを Google に登録する必要があります。

1. https://console.cloud.google.com/ を開き、上部のプロジェクト選択から **新しいプロジェクト** を作る（名前は自由。例：`meet-minutes`）
2. 左メニュー「API とサービス」→「ライブラリ」で **Google Docs API** を検索し、**有効にする**
3. 「API とサービス」→「OAuth 同意画面」（Google Auth Platform）を開いて設定する
   - アプリ名：自由（例：議事録ツール）、サポートメール：自分のアドレス
   - 対象（ユーザーの種類）：**外部**
   - **テストユーザー** に自分の Google アカウントを追加する（これを忘れるとログインできません）
4. 「クライアント」（認証情報）→「クライアントを作成」→ OAuth クライアント ID
   - アプリケーションの種類：**デスクトップ アプリ**
5. 作成後に表示される **JSON をダウンロード** し、名前を `credentials.json` に変えてこのフォルダに置く

初めて実行するとブラウザが開き、Google のログイン画面が出ます。
「このアプリは Google で確認されていません」と表示されたら、「続行」を押してください（自分で作ったアプリなので問題ありません）。
ログインすると `token.json` が作られ、次回からはログイン不要になります。

---

## 使い方

まずは **サンプルテキストで要約だけ試す** のがおすすめです（Whisper の料金がかからず、Google の設定も不要）。

```powershell
# ステップ1：要約だけ試す（OpenAI キーと Google 設定は不要）
C:\Users\kt061\.venvs\meet-minutes\Scripts\python main.py --text sample_transcript.txt --no-docs

# ステップ2：Google ドキュメントへの保存まで試す
C:\Users\kt061\.venvs\meet-minutes\Scripts\python main.py --text sample_transcript.txt --title "定例ミーティング 議事録"

# ステップ3：録音ファイルから全部やる
C:\Users\kt061\.venvs\meet-minutes\Scripts\python main.py "C:\Users\kt061\Downloads\会議の録画.mp4"

# チャットログも一緒に渡す（議事録の参考情報になる）
C:\Users\kt061\.venvs\meet-minutes\Scripts\python main.py 会議.mp4 --chat chat.txt
```

---

## 録音ファイルの入手方法

- **Google Meet の録画機能**：会議中に「録画を開始」すると、終了後に Google ドライブの「Meet Recordings」フォルダに mp4 が保存されます。そこからダウンロードしてください。
  - ※ 録画機能は Google Workspace の有料プラン（Business Standard 以上など）で使えます。個人の無料 Gmail では使えません。
- **録画機能がない場合**：Windows の「サウンド レコーダー」アプリや OBS などで PC の音声を録音してください。
- **Meet の文字起こし機能（トランスクリプト）やチャットログ** がある場合は、`--text` で渡せば Whisper を使わずに議事録を作れます。

### 録音ファイルが大きいとき

Whisper API は1ファイル **25MB まで** です。Meet の録画（動画）はすぐに超えます。
**ffmpeg** をインストールしておくと、25MB を超えたときに自動で「音声だけの小さな mp3」に変換します（約100分まで対応）。

```powershell
winget install ffmpeg
```

インストール後、ターミナルを開き直してください。

---

## 料金の目安

| 部品 | 目安 |
|---|---|
| Whisper | 1分あたり約 $0.006（1時間の会議で約 $0.36 ≒ 50円ほど） |
| Claude（claude-opus-5-5） | 1時間の会議で数十円程度（入力 $4 / 出力 $20 ／ 100万トークンあたり） |
| Google Docs API | 無料 |

## 補足：Claude の設定について

`summarize.py` の Claude 呼び出しには次の設定を入れています。

- **ストリーミング**：長い会議でも通信がタイムアウトしないよう、応答を少しずつ受け取る
- **fallbacks（フォールバック）**：まれに Claude が安全上の理由で回答を断ることがあり、そのとき自動で別のモデルに切り替えて再実行する。不要なら `betas=` と `fallbacks=` の2行を消してください

## これから発展させるなら

- Google ドライブの「Meet Recordings」から最新の録画を自動で取ってくる（Google Drive API）
- 完成した議事録の URL を Slack やメールで共有する
- 話者（誰が話したか）を区別する文字起こしにする
