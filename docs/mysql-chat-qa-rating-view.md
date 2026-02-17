# MySQL 视图：聊天问答 + 机器人 + 点赞点踩

目标：在 MySQL 中用一个视图查询“谁在什么时候问了什么问题，并得到了什么回答，机器人是谁，是否有点赞/点踩记录”。  
适用前提：你的 Open WebUI 数据已落在 MySQL，并且包含如下表：`chat`、`feedback`、`user`（表名/字段与 Open WebUI 默认一致）。

## 关键表说明（Open WebUI 默认）

- `chat`
  - `id`：chat_id
  - `user_id`：发起对话的用户 id
  - `title`：对话标题
  - `chat`：JSON，核心在 `$.history.messages`（对象：message_id -> message JSON）
- `feedback`
  - `type`：其中 `rating` 表示点赞点踩
  - `data`：JSON，常见键：`rating`（1/-1）、`comment`、`reason`
  - `meta`：JSON，常见键：`chat_id`、`message_id`
  - `user_id`：做出点赞点踩的用户 id
- `user`
  - `id`、`email`、`name`、`username`

## 创建视图

以下视图会“展开 chat.chat 的 history.messages”，把 **assistant 回复** 与其 **parentId 指向的 user 问题**配对，并左连接对应的点赞/点踩反馈。

> 要求：MySQL 8.0+（使用 `JSON_TABLE` / `JSON_KEYS`）。

```sql
CREATE OR REPLACE VIEW `vw_chat_qa_rating` AS
SELECT
  a.chat_id,
  a.chat_title,

  a.chat_user_id                       AS user_id,
  u.email                              AS user_email,
  u.name                               AS user_name,
  u.username                           AS user_username,

  q.msg_id                             AS question_message_id,
  JSON_UNQUOTE(q.content_json)         AS question,
  q.ts                                 AS question_ts,
  CASE
    WHEN q.ts IS NULL THEN NULL
    WHEN q.ts >= 20000000000 THEN FROM_UNIXTIME(q.ts / 1000)
    ELSE FROM_UNIXTIME(q.ts)
  END                                  AS question_at,

  a.msg_id                             AS answer_message_id,
  JSON_UNQUOTE(a.content_json)         AS answer,
  a.ts                                 AS answer_ts,
  CASE
    WHEN a.ts IS NULL THEN NULL
    WHEN a.ts >= 20000000000 THEN FROM_UNIXTIME(a.ts / 1000)
    ELSE FROM_UNIXTIME(a.ts)
  END                                  AS answer_at,

  a.model                              AS bot_model,

  f.id                                 AS feedback_id,
  f.user_id                            AS feedback_user_id,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.rating')) AS SIGNED) AS rating,
  CASE
    WHEN JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.rating')) = '1'  THEN 'up'
    WHEN JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.rating')) = '-1' THEN 'down'
    ELSE NULL
  END                                  AS rating_label,
  JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.comment')) AS rating_comment,
  JSON_UNQUOTE(JSON_EXTRACT(f.data, '$.reason'))  AS rating_reason,
  f.created_at                          AS feedback_ts,
  FROM_UNIXTIME(f.created_at)           AS feedback_at
FROM
  (
    SELECT
      m.chat_id,
      m.chat_title,
      m.chat_user_id,
      m.msg_id,
      m.parent_id,
      m.role,
      m.model,
      m.ts,
      m.content_json
    FROM
      (
        SELECT
          t.chat_id,
          t.chat_title,
          t.chat_user_id,
          t.msg_id,
          JSON_UNQUOTE(JSON_EXTRACT(t.msg_json, '$.role'))     AS role,
          JSON_UNQUOTE(JSON_EXTRACT(t.msg_json, '$.parentId')) AS parent_id,
          JSON_UNQUOTE(JSON_EXTRACT(t.msg_json, '$.model'))    AS model,
          CAST(JSON_EXTRACT(t.msg_json, '$.timestamp') AS UNSIGNED) AS ts,
          JSON_EXTRACT(t.msg_json, '$.content')                AS content_json
        FROM
          (
            SELECT
              c.id    AS chat_id,
              c.title AS chat_title,
              c.user_id AS chat_user_id,
              jt.msg_id AS msg_id,
              JSON_EXTRACT(c.chat, CONCAT('$.history.messages."', jt.msg_id, '"')) AS msg_json
            FROM `chat` c
            JOIN JSON_TABLE(
              JSON_KEYS(c.chat, '$.history.messages'),
              '$[*]' COLUMNS (msg_id VARCHAR(64) PATH '$')
            ) jt
            WHERE JSON_EXTRACT(c.chat, '$.history.messages') IS NOT NULL
          ) t
      ) m
    WHERE m.role = 'assistant'
  ) a
LEFT JOIN
  (
    SELECT
      m.chat_id,
      m.msg_id,
      m.role,
      m.ts,
      m.content_json
    FROM
      (
        SELECT
          t.chat_id,
          t.msg_id,
          JSON_UNQUOTE(JSON_EXTRACT(t.msg_json, '$.role'))     AS role,
          CAST(JSON_EXTRACT(t.msg_json, '$.timestamp') AS UNSIGNED) AS ts,
          JSON_EXTRACT(t.msg_json, '$.content')                AS content_json
        FROM
          (
            SELECT
              c.id AS chat_id,
              jt.msg_id AS msg_id,
              JSON_EXTRACT(c.chat, CONCAT('$.history.messages."', jt.msg_id, '"')) AS msg_json
            FROM `chat` c
            JOIN JSON_TABLE(
              JSON_KEYS(c.chat, '$.history.messages'),
              '$[*]' COLUMNS (msg_id VARCHAR(64) PATH '$')
            ) jt
            WHERE JSON_EXTRACT(c.chat, '$.history.messages') IS NOT NULL
          ) t
      ) m
    WHERE m.role = 'user'
  ) q
  ON q.chat_id = a.chat_id AND q.msg_id = a.parent_id
LEFT JOIN `feedback` f
  ON f.`type` = 'rating'
  AND JSON_UNQUOTE(JSON_EXTRACT(f.meta, '$.chat_id')) = a.chat_id
  AND JSON_UNQUOTE(JSON_EXTRACT(f.meta, '$.message_id')) = a.msg_id
LEFT JOIN `user` u
  ON u.id = a.chat_user_id;
```

## 常用查询方法

### 1）查最近 7 天所有问答（含点赞点踩）

```sql
SELECT *
FROM vw_chat_qa_rating
WHERE answer_at >= NOW() - INTERVAL 7 DAY
ORDER BY answer_at DESC;
```

### 2）只看点过赞/踩的问答

```sql
SELECT *
FROM vw_chat_qa_rating
WHERE rating IN (1, -1)
ORDER BY feedback_at DESC;
```

### 3）按机器人（模型）筛选

```sql
SELECT *
FROM vw_chat_qa_rating
WHERE bot_model = 'gpt-4o-mini'
ORDER BY answer_at DESC;
```

### 4）按用户筛选（email / name）

```sql
SELECT *
FROM vw_chat_qa_rating
WHERE user_email = 'someone@company.com'
ORDER BY answer_at DESC;
```

### 5）统计每个机器人点赞/点踩数量

```sql
SELECT
  bot_model,
  SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END)  AS up_cnt,
  SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) AS down_cnt
FROM vw_chat_qa_rating
GROUP BY bot_model
ORDER BY up_cnt DESC, down_cnt ASC;
```

## 注意事项

- `chat.chat` 的 `$.history.messages` 是“对象（map）”，message_id 通常是 UUID（包含 `-`），所以 JSON 路径里必须使用 `"...“` 引号：`$.history.messages."{message_id}"`。
- `message.content` 有时是字符串，有时是数组/对象；视图里用 `JSON_UNQUOTE(content_json)`，遇到非字符串会返回该 JSON 的字符串化结果。
- `message.timestamp` 在不同版本可能是秒或毫秒；视图里用 `>= 20000000000` 作为“毫秒时间戳”判断并除以 1000。

