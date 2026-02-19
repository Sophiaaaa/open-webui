# MySQL 视图：BKM 原因/行动建议 点赞点踩统计

本项目会把 BKM 的“原因/行动建议”级别点赞点踩写入 `feedback` 表（`type = 'bkm_item_rating'`）。你可以在 MySQL 里创建一个视图，把 JSON 字段展开，方便做统计查询。

## 视图定义

```sql
CREATE OR REPLACE VIEW vw_bkm_item_rating AS
SELECT
  f.id AS feedback_id,
  f.user_id,
  f.created_at,
  JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.rating'))   AS rating,   -- 'up' / 'down'
  JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.kind'))     AS kind,     -- 'cause' / 'action'
  JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.entry_id')) AS entry_id,
  JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.text'))     AS text,
  JSON_EXTRACT(f.data, '$.score')                  AS score,
  JSON_UNQUOTE(JSON_EXTRACT(f.meta, '$.page'))     AS page,     -- 'chat' / 'bkm'
  JSON_UNQUOTE(JSON_EXTRACT(f.meta, '$.chat_id'))  AS chat_id,
  JSON_UNQUOTE(JSON_EXTRACT(f.meta, '$.message_id')) AS message_id,
  JSON_EXTRACT(f.meta, '$.docs')                   AS docs
FROM feedback f
WHERE f.type = 'bkm_item_rating';
```

## 常用统计示例

### 1) 按原因/行动建议汇总（TOP）

```sql
SELECT
  kind,
  entry_id,
  text,
  SUM(rating = 'up')   AS up_count,
  SUM(rating = 'down') AS down_count,
  COUNT(*)             AS total
FROM vw_bkm_item_rating
GROUP BY kind, entry_id, text
ORDER BY up_count DESC, total DESC
LIMIT 50;
```

### 2) 按页面来源（chat vs bkm）统计

```sql
SELECT
  page,
  SUM(rating = 'up')   AS up_count,
  SUM(rating = 'down') AS down_count,
  COUNT(*)             AS total
FROM vw_bkm_item_rating
GROUP BY page
ORDER BY total DESC;
```
