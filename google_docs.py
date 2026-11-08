"""
④ 保存担当：議事録テキスト → Google ドキュメント

Google Docs API を使って新しいドキュメントを作り、議事録を書き込みます。
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 「Google ドキュメントの読み書き」だけを許可してもらう（必要最小限の権限）
SCOPES = ["https://www.googleapis.com/auth/documents"]

BASE_DIR = Path(__file__).parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # Google Cloud からダウンロードする「アプリの身分証」
TOKEN_FILE = BASE_DIR / "token.json"              # ログイン後に自動で作られる「通行証」


def get_credentials() -> Credentials:
    """
    Google にログインして、API を使う許可（認証情報）を取得する。
    初回だけブラウザが開いてログイン画面が出ます。2回目以降は token.json を使うので不要です。
    """
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # 期限切れなら自動で更新
        else:
            if not CREDENTIALS_FILE.exists():
                raise RuntimeError(
                    "credentials.json が見つかりません。README の「Google Cloud の設定」を行ってください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)  # ブラウザでログイン
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _utf16_len(text: str) -> int:
    """
    Google Docs は文字の位置を「UTF-16 の単位」で数えます。
    日本語の普通の文字は1、絵文字などは2になるので、その数え方で長さを求めます。
    """
    return len(text.encode("utf-16-le")) // 2


def build_requests(title: str, minutes: str) -> list[dict]:
    """
    ドキュメントに送る「編集命令」のリストを作る。
    1. 本文をまとめて挿入する
    2. 「## 」で始まる行を見出しに、「- 」で始まる行を箇条書きにする
       （「  - 」のように字下げされた行は、1段下がった箇条書きにする）
    """
    lines = [title] + minutes.splitlines()
    body_lines = []
    styles = []  # (開始位置, 終了位置, 種類) を記録しておく

    index = 1  # Google Docs の本文は位置 1 から始まる
    for i, line in enumerate(lines):
        kind = "normal"
        stripped = line.lstrip()
        if i == 0:
            kind = "title"
        elif line.startswith("## "):
            kind = "heading"
            line = line[3:]
        elif stripped.startswith("- "):
            kind = "bullet"
            # Google Docs では、行頭のタブの数が箇条書きの段の深さになる（スペース2つ = 1段）
            level = (len(line) - len(stripped)) // 2
            line = "\t" * level + stripped[2:]

        text = line + "\n"
        length = _utf16_len(text)
        if kind != "normal":
            # 箇条書きが続いているときは、1つのまとまり（リスト）としてつなげる
            if kind == "bullet" and styles and styles[-1][2] == "bullet" and styles[-1][1] == index:
                styles[-1] = (styles[-1][0], index + length, "bullet")
            else:
                styles.append((index, index + length, kind))
        body_lines.append(text)
        index += length

    requests = [{"insertText": {"location": {"index": 1}, "text": "".join(body_lines)}}]

    # 箇条書きにするとき行頭のタブが消えて、それより後ろの文字の位置がずれる。
    # なので、ドキュメントの「後ろから順に」書式をつけて、ずれの影響を受けないようにする。
    style_names = {"title": "TITLE", "heading": "HEADING_2"}
    for start, end, kind in reversed(styles):
        rng = {"startIndex": start, "endIndex": end}
        if kind in style_names:
            requests.append({
                "updateParagraphStyle": {
                    "range": rng,
                    "paragraphStyle": {"namedStyleType": style_names[kind]},
                    "fields": "namedStyleType",
                }
            })
        else:  # bullet
            requests.append({
                "createParagraphBullets": {
                    "range": rng,
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                }
            })
    return requests


def save_to_google_docs(title: str, minutes: str) -> str:
    """議事録を新しい Google ドキュメントとして保存し、その URL を返す。"""
    service = build("docs", "v1", credentials=get_credentials())

    # 1. 空のドキュメントを作る
    doc = service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # 2. 本文と書式をまとめて書き込む
    service.documents().batchUpdate(
        documentId=doc_id, body={"requests": build_requests(title, minutes)}
    ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"
