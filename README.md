# 厚労省 一次情報収集ボット

厚生労働省の公式RSSから新着を取得し、Discordに通知するシステムです。

## 対象ソース（一次情報）

| ID | 名前 | URL |
|----|------|-----|
| mhlw_news | 厚生労働省 新着情報 | https://www.mhlw.go.jp/stf/news.rdf |
| mhlw_kinkyu | 厚生労働省 緊急情報 | https://www.mhlw.go.jp/stf/kinkyu.rdf |

## フォルダ構成

```
primary-info-bot/
├── main.py              ← スタート（これを実行）
├── config/
│   ├── sources.yaml     ← 情報源リスト
│   └── keywords.yaml    ← 重要度キーワード
├── fetch/               ← 取得
├── process/             ← 整理（重複・分類・重要度）
├── notify/              ← 通知
├── data/                ← 既読メモ（GitHub Actionsが更新）
└── .github/workflows/   ← 自動実行
```

## ローカルで試す（3ステップ）

### 1. 準備

```powershell
cd primary-info-bot
pip install -r requirements.txt
```

### 2. 初回実行（既存記事を既読登録、通知なし）

```powershell
python main.py
```

### 3. Discord通知を試す

1. Discord でサーバーを開く
2. チャンネル設定 → 連携サービス → Webhook を作成
3. URLをコピーして環境変数にセット

```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
python main.py
```

2回目以降、新着があれば Discord に届きます。

## GitHub Actions で自動化

1. このフォルダを GitHub リポジトリに push
2. リポジトリ Settings → Secrets → Actions → New secret
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: Webhook URL
3. Actions タブ → 「厚労省 新着チェック」→ Run workflow（手動テスト）
4. 以降、1時間ごとに自動実行

## 情報源を増やす

`config/sources.yaml` に1ブロック追加するだけ（コード変更不要）。

```yaml
  - id: 任意のID
    name: 表示名
    genre: 政治・行政
    type: rss
    url: https://...
    priority: high
    enabled: true
```

## トラブル

| 症状 | 対処 |
|------|------|
| 初回に大量通知 | 初回は通知しない設計。`data/seen_ids.json` を消すと再び初回扱い |
| Discord に届かない | `DISCORD_WEBHOOK_URL` が正しいか確認 |
| Actions が失敗 | Secrets に Webhook URL が入っているか確認 |
