"""
② 文字起こし担当：音声ファイル → テキスト

OpenAI の Whisper API に音声ファイルを送ると、話している内容を文字にして返してくれます。
"""

import os
import shutil
import subprocess
from pathlib import Path

from openai import OpenAI

# Whisper API が一度に受け付けられるファイルサイズの上限（25MB）
MAX_BYTES = 25 * 1024 * 1024


def find_ffmpeg() -> str | None:
    """
    ffmpeg の場所を探す。
    まず PATH（コマンドの置き場所リスト）から探し、見つからなければ
    winget がインストールする場所を直接探す。
    （ターミナルを開き直していないと、PATH が古いままのことがあるため）
    """
    found = shutil.which("ffmpeg")
    if found:
        return found

    winget_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    candidates = sorted(winget_dir.glob("*FFmpeg*/*/bin/ffmpeg.exe"))
    return str(candidates[-1]) if candidates else None  # 複数あれば新しいバージョンを使う


def shrink_audio(src: Path, out_dir: Path) -> Path:
    """
    ファイルが25MBを超えるとき、ffmpeg（音声・動画変換ソフト）で
    「音声だけ・モノラル・低ビットレートの mp3」に変換して小さくする。
    32kbps の mp3 なら、約100分の会議でも25MB以内に収まります。
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError(
            f"ファイルが {src.stat().st_size / 1024 / 1024:.1f}MB あり、Whisper の上限（25MB）を超えています。\n"
            "ffmpeg をインストールすると自動で小さくできます（README の「録音ファイルが大きいとき」を参照）。"
        )

    out_path = out_dir / f"{src.stem}_compressed.mp3"
    print(f"  ファイルが大きいので ffmpeg で圧縮します → {out_path.name}")
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(src),
            "-vn",          # 映像を捨てる（音声だけ残す）
            "-ac", "1",     # モノラルにする
            "-ar", "16000", # サンプリングレートを下げる（人の声には十分）
            "-b:a", "32k",  # ビットレートを下げる
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    if out_path.stat().st_size > MAX_BYTES:
        raise RuntimeError("圧縮しても25MBを超えました。会議を前半・後半に分けて実行してください。")
    return out_path


def transcribe(audio_path: Path, out_dir: Path) -> str:
    """音声ファイルを文字起こしして、テキストを返す。"""
    if audio_path.stat().st_size > MAX_BYTES:
        audio_path = shrink_audio(audio_path, out_dir)

    # OpenAI() は環境変数 OPENAI_API_KEY から自動で API キーを読み込みます
    client = OpenAI()

    # ファイルを「バイナリモード（rb）」で開いて API に送る
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ja",  # 日本語だと伝えると精度が上がる
        )
    return result.text
