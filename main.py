"""
議事録自動作成ツール（司令塔）

① 録音ファイル（または文字起こし済みテキスト）を受け取る
② Whisper で文字起こし
③ Claude で議事録に要約
④ Google ドキュメントに保存

使い方の例：
  python main.py 録音.mp4                       # 音声から全部やる
  python main.py --text sample_transcript.txt   # 文字起こし済みテキストから（②を飛ばす）
  python main.py 録音.mp4 --no-docs             # Google ドキュメントに保存せず、手元のファイルだけ作る
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"


def main() -> None:
    # Windows のターミナルで日本語が文字化けしないようにする
    sys.stdout.reconfigure(encoding="utf-8")

    # コマンドラインの引数（実行時に渡す情報）を定義する
    parser = argparse.ArgumentParser(description="会議の録音から議事録を作って Google ドキュメントに保存します")
    parser.add_argument("audio", nargs="?", help="録音ファイルのパス（mp3 / m4a / mp4 / wav など）")
    parser.add_argument("--text", help="文字起こし済みテキストやチャットログのファイル（指定すると文字起こしを飛ばす）")
    parser.add_argument("--chat", help="Meet のチャットログのファイル（任意。議事録の参考情報として渡す）")
    parser.add_argument("--title", help="議事録のタイトル（省略すると日付から自動で作る）")
    parser.add_argument("--no-docs", action="store_true", help="Google ドキュメントに保存しない")
    parser.add_argument("--minutes", help="作成済みの議事録ファイル（output/*_minutes.md）を Google ドキュメントに保存だけする")
    args = parser.parse_args()

    # .env ファイルに書いた API キーを環境変数として読み込む
    load_dotenv(BASE_DIR / ".env")

    # 作成済みの議事録を保存だけするモード（文字起こし・要約をやり直さないので料金がかからない）
    if args.minutes:
        text = Path(args.minutes).read_text(encoding="utf-8")
        first, _, rest = text.partition("\n")
        title = args.title or (first[2:].strip() if first.startswith("# ") else "議事録")
        minutes = rest.strip() if first.startswith("# ") else text

        from google_docs import save_to_google_docs

        print("Google ドキュメントに保存中...")
        print(f"  → 完成しました！ {save_to_google_docs(title, minutes)}")
        return

    if not args.audio and not args.text:
        parser.error("録音ファイルか --text のどちらかを指定してください")

    # 必要な API キーが .env に正しく書かれているか、最初にチェックする
    needed = ["ANTHROPIC_API_KEY"] + ([] if args.text else ["OPENAI_API_KEY"])
    for name in needed:
        key = os.environ.get(name, "")
        if not key or not key.isascii() or "ここに" in key:
            sys.exit(f"エラー: .env の {name} が設定されていません（見本の文字のままの可能性があります）。")

    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    title = args.title or f"議事録 {datetime.now():%Y-%m-%d %H:%M}"

    # ---- ① と ② 文字起こし ----
    if args.text:
        print(f"[1/3] テキストを読み込みます: {args.text}")
        transcript = Path(args.text).read_text(encoding="utf-8")
    else:
        from transcribe import transcribe

        print(f"[1/3] 文字起こし中...（会議の長さによって数分かかります）: {args.audio}")
        transcript = transcribe(Path(args.audio), OUTPUT_DIR)
        # 途中結果を保存しておく（後の工程で失敗しても、文字起こしをやり直さずに済む）
        transcript_path = OUTPUT_DIR / f"{stamp}_transcript.txt"
        transcript_path.write_text(transcript, encoding="utf-8")
        print(f"      → 保存しました: {transcript_path}")

    chat_log = Path(args.chat).read_text(encoding="utf-8") if args.chat else ""

    # ---- ③ 要約 ----
    from summarize import summarize

    print("[2/3] Claude で議事録を作成中...")
    extra = f"会議中のチャットログ:\n{chat_log}" if chat_log else ""
    minutes = summarize(transcript, extra)
    minutes_path = OUTPUT_DIR / f"{stamp}_minutes.md"
    minutes_path.write_text(f"# {title}\n\n{minutes}\n", encoding="utf-8")
    print(f"      → 保存しました: {minutes_path}")

    # ---- ④ Google ドキュメントに保存 ----
    if args.no_docs:
        print("[3/3] --no-docs が指定されたので、Google ドキュメントへの保存は飛ばします")
    else:
        from google_docs import save_to_google_docs

        print("[3/3] Google ドキュメントに保存中...")
        url = save_to_google_docs(title, minutes)
        print(f"      → 完成しました！ {url}")


if __name__ == "__main__":
    main()
