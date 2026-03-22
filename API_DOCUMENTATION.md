# BOOKOFF 在庫確認 API ドキュメント

## 概要

BOOKOFF オンラインストアから商品の在庫状況をリアルタイムで確認するためのバックエンド API。

## エンドポイント

### 1. ヘルスチェック

```
GET /health
```

**説明**: API サーバーの稼働状況を確認

**レスポンス例**:
```json
{
  "status": "healthy"
}
```

---

### 2. 商品検索

```
POST /api/search
```

**説明**: BOOKOFF で商品を検索し、詳細情報を取得

**リクエスト**:
```json
{
  "query": "呪術廻戦"
}
```

**レスポンス例**:
```json
{
  "query": "呪術廻戦",
  "count": 15,
  "results": [
    {
      "title": "呪術廻戦(28) ジャンプC",
      "price": "¥572円",
      "url": "https://shopping.bookoff.co.jp/new/0020384430",
      "image_url": "https://content.bookoff.co.jp/goodsimages/LL/002038/0020384430LL.jpg"
    },
    ...
  ]
}
```

---

### 3. 在庫確認 ✨ **NEW**

```
POST /api/stock
```

**説明**: 指定したキーワードの商品が BOOKOFF に在庫があるかを確認

**リクエスト**:
```json
{
  "query": "呪術廻戦"
}
```

**レスポンス例（在庫あり - 完全一致）**:
```json
{
  "keyword": "呪術廻戦",
  "in_stock": true,
  "matching_count": 24,
  "match_type": "完全一致",
  "products": [
    {
      "title": "呪術廻戦(28) ジャンプC",
      "price": "¥572円",
      "url": "https://shopping.bookoff.co.jp/new/0020384430",
      "image_url": "https://content.bookoff.co.jp/goodsimages/LL/002038/0020384430LL.jpg"
    },
    ...
  ]
}
```

**レスポンス例（在庫あり - 部分一致）**:
```json
{
  "keyword": "呪術",
  "in_stock": true,
  "matching_count": 28,
  "match_type": "部分一致",
  "products": [...]
}
```

**レスポンス例（在庫なし）**:
```json
{
  "keyword": "續々 さすらいエマノン",
  "in_stock": false,
  "matching_count": 0,
  "match_type": "在庫なし",
  "products": []
}
```

---

## レスポンスフィールド説明

### StockCheckResponse（在庫確認）

| フィールド | 型 | 説明 |
|-----------|----|----|
| `keyword` | string | 検索キーワード |
| `in_stock` | boolean | 在庫の有無（true=あり, false=なし） |
| `matching_count` | integer | マッチした商品数 |
| `match_type` | string | マッチタイプ（"完全一致", "部分一致", "在庫なし"） |
| `products` | array | マッチした商品情報（最大10件） |

---

## 使用例

### Python

```python
import requests

url = "http://localhost:8000/api/stock"
payload = {"query": "呪術廻戦"}

response = requests.post(url, json=payload)
result = response.json()

if result["in_stock"]:
    print(f"✅ 在庫あり: {result['matching_count']} 件")
    for product in result["products"][:3]:
        print(f"  - {product['title']}")
else:
    print(f"❌ 在庫なし")
```

### cURL

```bash
curl -X POST http://localhost:8000/api/stock \
  -H "Content-Type: application/json" \
  -d '{"query": "呪術廻戦"}'
```

### JavaScript / Fetch API

```javascript
const checkStock = async (keyword) => {
  const response = await fetch("http://localhost:8000/api/stock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: keyword })
  });
  
  const result = await response.json();
  
  if (result.in_stock) {
    console.log(`✅ 在庫あり: ${result.matching_count}件`);
  } else {
    console.log(`❌ 在庫なし`);
  }
  
  return result;
};

checkStock("呪術廻戦");
```

---

## マッチタイプの説明

### 完全一致
- キーワードをスペースで分割し、**すべての部分**がタイトルに含まれている
- 例：「呪術 廻戦」→ 「呪術」と「廻戦」の両方を含む商品

### 部分一致
- キーワードの**いずれかの部分**がタイトルに含まれている
- 例：「呪術」→ 「呪術」を含む任意の商品

### 在庫なし
- キーワード関連の商品が見つからない
- BOOKOFF に在庫がないか、取り扱いがない

---

## エラーレスポンス

**400 Bad Request**:
```json
{
  "detail": "検索クエリが入力されていません"
}
```

**503 Service Unavailable**:
```json
{
  "detail": "BOOKOFFサイトにアクセスできません: ..."
}
```

**500 Internal Server Error**:
```json
{
  "detail": "在庫確認処理でエラーが発生しました: ..."
}
```

---

## サーバー起動

```bash
cd /app/app/src
python3 backend.py
```

サーバーは `http://localhost:8000` で起動します。

### Swagger UI (インタラクティブドキュメント)
- URL: `http://localhost:8000/docs`

### ReDoc (API ドキュメント)
- URL: `http://localhost:8000/redoc`

---

## テスト

```bash
cd /app/app/labo
python3 test_stock_api.py
```
