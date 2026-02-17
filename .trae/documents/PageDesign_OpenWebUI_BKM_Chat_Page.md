# 页面设计：BKM 聊天页（Desktop-first）

## 1) Layout
- 桌面端采用 **双栏布局（CSS Grid）**：左侧“对话与答案”，右侧“PDF 来源阅读区”。
- Grid 建议：`grid-template-columns: minmax(520px, 1fr) 520px;`，中间间距 16px；整体高度占满可视区域。
- 移动端/窄屏（<1024px）：右侧来源区收起为 **Drawer/Tab**（“对话 / 来源”切换），默认展示对话。

## 2) Meta Information
- Title：BKM Chat Bot | Open WebUI
- Description：基于 BKM PDF/JSON 的 action & root cause 问答，支持来源页码跳转与反馈。
- Open Graph：`og:title` 同 Title；`og:description` 同 Description；`og:type=website`。

## 3) Global Styles（复用现有 Open WebUI 设计体系）
- 背景：浅灰（页面底色）+ 白色卡片（消息气泡/答案卡）。
- 字体：系统字体栈；正文 14–16px；标题 18px。
- 主色：沿用 Open WebUI 主色；链接色用于“来源页码”。
- 按钮：主按钮（发送）；次按钮（重置/打开来源）；icon 按钮（👍/👎）。
- Hover/Focus：按钮与来源链接提供可见 focus ring；PDF 页码链接 hover 下划线。

## 4) Page Structure
- 顶部 Header（固定）：页面标题“BKM Bot”、重置对话、（可选）数据版本标识（例如 JSON 更新时间）。
- 主体 Main（两栏）：
  - 左栏：消息列表 + 输入区。
  - 右栏：PDF Viewer + 当前引用列表（可点击跳页）。

## 5) Sections & Components

### 5.1 Header
- 左侧：页面标题 + 简短副标题（“基于 BKM PDF/JSON”）。
- 右侧：
  - “重置对话”按钮（清空当前会话 UI 状态）。
  - “打开来源”按钮（在窄屏时打开来源 Drawer）。

### 5.2 Chat Message List（左栏上半部分）
- 消息气泡区分 user / bot。
- Bot 消息支持 **结构化答案渲染**（建议按卡片渲染而非纯文本）：
  - AnswerSummary：1–2 行总览。
  - ItemCards（多条）：
    - ItemHeader：匹配主题/条目标题（来自 JSON 或由模型生成）。
    - Fields：
      - Action：可多条列表。
      - Root Cause：可多条列表，与 action 对应或按分组展示。
      - Evidence：引用摘录（来自 JSON，短文本）。
    - Sources：`source_pdf + page`，每个 page 为可点击链接。
- 每条 Bot 消息尾部：反馈区（👍/👎）+（可选）“补充原因”文本框（点踩后展开）。

### 5.3 Composer / Input（左栏底部固定）
- 多行输入框（Enter 发送，Shift+Enter 换行）。
- 发送按钮 + 加载态（发送后禁用输入与按钮）。
- 错误提示：以 inline banner 展示（例如“未检索到匹配条目，请换个问法”）。

### 5.4 Source Panel（右栏）
- 顶部：来源标题“BKM PDF”。
- PDF Viewer：使用 `<iframe>` 或内嵌 PDF 组件加载 `/bkm/assets/bkm.pdf`。
- 跳页逻辑：点击来源页码后，将 viewer URL 更新为 `.../bkm.pdf#page={n}` 并滚动聚焦。
- 引用列表：显示“本次回答引用了哪些页”（去重排序），点击同样触发跳页。

### 5.5 Interaction States
- 👍：记录“有帮助”，按钮高亮（可再次点击取消或提示已提交，二选一）。
- 👎：记录“无帮助”，展开原因输入（可选），提交后按钮高亮。
- 来源点击：高亮当前页码，右栏 viewer 聚焦。

### 5.6 Accessibility
- 所有 icon 按钮提供 aria-label（如“点赞此回答”“点踩此回答”）。
- 页码链接可键盘聚焦；焦点状态明显。
- PDF 区域提供“在新标签页打开 PDF”的备用链接。