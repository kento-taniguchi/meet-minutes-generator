"""
③ 要約担当：文字起こしテキスト → 議事録

Claude API に「この文字起こしを議事録にまとめて」とお願いして、結果を受け取ります。
"""

import anthropic

MODEL = "claude-opus-5-5"

# システムプロンプト：Claude に「あなたの役割」と「出力の形」を伝える指示文
SYSTEM_PROMPT = """あなたは会議の議事録を作成するアシスタントです。
渡される会議の文字起こし（またはチャットログ）を読み、社内で共有するための議事録を日本語で作成してください。

文字起こしには聞き間違いや言い直しが含まれます。文脈から明らかな誤りは直し、
内容が読み取れない部分は推測で補わず「（不明瞭）」と書いてください。
発言にない決定事項や担当者を作らないでください。

出力は次の形式に従ってください。見出しの行は「## 」で始め、箇条書きの行は「- 」で始めます。
それ以外の記号（** や # の重ね書きなど）は使わないでください。

## 会議の概要
（2〜3文で、何の会議で何が話されたか）

## 議題と議論の内容
- （議題ごとに、主な意見や論点）

## 決定事項
- （決まったこと。なければ「なし」）

## ToDo（担当者・期限）
- （やること / 担当者 / 期限。発言から分からない項目は「未定」）

## 次回に持ち越す課題
- （未解決の論点。なければ「なし」）
"""


def summarize(transcript: str, extra_info: str = "") -> str:
    """文字起こしテキストを Claude に渡して、議事録のテキストを返す。"""
    # Anthropic() は環境変数 ANTHROPIC_API_KEY から自動で API キーを読み込みます
    client = anthropic.Anthropic()

    user_message = f"以下の会議の記録から議事録を作成してください。\n\n"
    if extra_info:
        user_message += f"【補足情報】\n{extra_info}\n\n"
    user_message += f"【会議の記録】\n{transcript}"

    # 長い会議だと返答に時間がかかるので「ストリーミング」で受け取ります。
    # （少しずつ受け取ることで、途中で通信がタイムアウトするのを防げます）
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        thinking={"type": "adaptive"},       # 必要に応じて Claude が考えてから答える
        output_config={"effort": "medium"},  # 考える深さ（low / medium / high ...）
        # 万一 Claude が安全上の理由で回答を断った場合に、別のモデルで自動再実行する設定
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        response = stream.get_final_message()

    # 応答が途中で終わっていないかチェック
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude が要約を断りました。入力内容を確認してください。")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("出力が長すぎて途中で切れました。")

    # 応答は「ブロック」のリストで返ってくるので、テキストのブロックだけをつなげる
    return "".join(block.text for block in response.content if block.type == "text").strip()
