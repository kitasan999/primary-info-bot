# 一次情報 → Discord 通知ボット

日本の一次情報（経済・政策）を RSS から取得し、**重要なものだけ** Gemini で解説して **Discord** に通知する仕組みです。

## この仕組みでやること

1. TDnet・内閣府・厚労省・防衛省などの RSS から新着を取得
2. タイトル＋要約に「重要キーワード」が含まれるものだけ残す
3. Gemini が中学生向けの解説を生成
4. Discord Webhook で通知

全部送るのではなく、**重要そうなものだけ**届きます。

## フォルダ構成

```
primary-info-bot/
├── .github/workflows/
│   └── notify.yml       ← GitHub Actions（定期実行・手動実行）
├── scripts/
│   └── notify.py        ← メインスクリプト
├── requirements.txt
└── README.md
```

（従来の `main.py` ベースの厚労省ボットも残っています。こちらは `collect.yml` で動きます。）

## 必要な Secrets（GitHub）

リポジトリの **Settings → Secrets and variables → Actions** で次を登録してください。

| Name | 内容 |
|------|------|
| `DISCORD_WEBHOOK_URL` | Discord Webhook の URL |
| `GEMINI_API_KEY` | Google AI Studio の API キー |

## Discord Webhook の作り方

1. 通知したい Discord サーバーを開く
2. チャンネル名の横 **⚙ 設定** → **連携サービス** → **ウェブフック**
3. **新しいウェブフック** を作成
4. 名前を付けて **Webhook URL をコピー**
5. GitHub Secrets の `DISCORD_WEBHOOK_URL` に貼り付け

## Gemini API キーの取得

1. [Google AI Studio](https://aistudio.google.com/) を開く
2. **Get API key** からキーを発行
3. GitHub Secrets の `GEMINI_API_KEY` に登録

## 手動実行（GitHub Actions）

1. GitHub リポジトリの **Actions** タブを開く
2. 左メニューから **「一次情報 → Discord 通知」** を選択
3. **Run workflow** → **Run workflow**

## ローカルで試す

```powershell
cd primary-info-bot
pip install -r requirements.txt

$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
$env:GEMINI_API_KEY = "your-gemini-api-key"
python scripts/notify.py
```

重要な新着がなければ、何も通知せず終了します。

## 実行スケジュール

GitHub Actions が **毎日 3 回**（日本時間）自動実行します。

| 日本時間 | 内容 |
|----------|------|
| 07:00 | 朝のチェック |
| 12:00 | 昼のチェック |
| 20:00 | 夜のチェック |

## キーワードの追加・削除

`scripts/notify.py` の先頭付近を編集します。

```python
ECONOMY_KEYWORDS = [
    "業績予想",
    "上方修正",
    # ここに追加
]

POLICY_KEYWORDS = [
    "防衛",
    "予算",
    # ここに追加
]
```

## 情報源（RSS）の追加

同じく `scripts/notify.py` の `FEEDS` リストに 1 行追加するだけです。

```python
FEEDS = [
    {"name": "表示名", "url": "https://..."},
]
```

## 通知の形式（例）

```
【重要一次情報】
（タイトル）

【一言で言うと】
...

【どういうこと？】
...

【なぜ大事？】
...

元の発表 → https://...
```

## トラブル

| 症状 | 対処 |
|------|------|
| Actions が失敗 | Secrets に URL と API キーが入っているか確認 |
| 通知が来ない | 直近 6 時間にキーワード一致の新着がなかった可能性 |
| Gemini エラー | API キーが有効か、利用制限に達していないか確認 |
| Discord エラー | Webhook URL が削除・無効化されていないか確認 |
