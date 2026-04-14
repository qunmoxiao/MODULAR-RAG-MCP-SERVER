---
name: review-session-summary
description: "Summarizes the user's latest answers vs reference key points per question (project-review bank IDs 1-xx/2A-xx etc.), adds a concise 推荐答题 (model interview answer) for复习口播, merges into rolling SESSION_LOG, outputs progress dashboard. Use when user says '总结答题', '复习总结', '学习日志', '题解归档', '答题记录', '复盘汇总', 'session summary', '推荐回答', '标准答', '我的错题', '最近答得怎样', or asks to persist/sync Q&A recap with project-review or project-learner."
---

# Review Session Summary — 答题与学习进度归档

## Goal

Build a **single rolling log** of, for each question ID touched in review:

- **我的最新回答**（可原文或摘要，摘要优先省 token）
- **参考要点**（摘自 `question_bank.md`「参考答案要点」或当轮讲解，2–5 条 bullet）
- **推荐答题**（见下节；**必填**，便于用户背诵复习）
- **日期**、可选 **掌握度**（自评 1–5 或 优/良/及格/需复习）
- 可选 **薄弱点一句话**

### 推荐答题（Model answer）撰写规则

- **用途**：给用户一段可直接用于面试/复述的**短口播**，不是 bullet 扩写。  
- **长度**：约 **80–220 字**（普通话约 **30–90 秒**）；复杂题可到 **280 字**。  
- **结构建议**（按需选用，不必标题）：先用一句话点题 → 分 2–3 句展开技术点 → 最后一句收束到**本项目**（模块名 / 配置 / 脚本名之一即可）。  
- **语气**：第一人称「我/本项目」或客观「该项目」均可；避免堆砌生僻英文缩写，必要时中文解释一下。  
- **来源**：以 `question_bank.md` 参考答案要点为准，可结合 `DEV_SPEC.md`、代码路径一句带过；**不要编造**仓库不存在的模块名。  
- **与「参考要点」关系**：要点 = 判分草稿；推荐答题 = **串起来的标准叙述**，两者都要写入 SESSION_LOG。

Optionally **sync header stats** from:

- `.github/skills/project-review/review_progress.md`
- `.github/skills/project-learner/references/LEARNING_PROGRESS.md`

All user-facing text: **中文**. Internal steps: English OK.

---

## Phase 1 — Locate input

1. Read existing log: `.github/skills/review-session-summary/references/SESSION_LOG.md` (create from `references/SESSION_LOG_TEMPLATE.md` structure if missing).
2. If user says "只看总览" / "输出仪表盘": only read SESSION_LOG + the two progress files above, then Phase 4 (output) only.
3. Otherwise infer **which questions** to update from:
   - Explicit list from user (e.g. `1-05`, `2B-01`, `D3.2`), or
   - Current conversation: numbered `project-review` items (`1-0x`, `2A-xx`…) or `project-learner` IDs (`Dx.y`).

---

## Phase 2 — Merge rules (latest wins)

- **One latest entry per question ID** in the log. New session **overwrites** the previous block for the same ID (keep history only if user explicitly asks for "保留历史版本"; then append dated subsection under that ID).
- Map **D1.1** etc. to a **知识点** line; link to domain table in LEARNING_PROGRESS if helpful.
- **参考要点**: Prefer the "参考答案要点" column from `question_bank.md`; shorten to 2–5 bullets max in the log.
- **推荐答题**: After bullets, **always** add one `推荐答题` paragraph per ID (see writing rules above). If user already gave a strong answer, you may base the 推荐答题 on theirs + gap-fill; otherwise synthesize from question_bank.

---

## Phase 3 — Write SESSION_LOG.md

1. Update `## 快速总览` table: 题号, 最近更新日期, 掌握度（若未知填 —）.
2. For each updated ID, write or replace `### {题号} {简短题述}` block with:

```markdown
### 1-05 五类可插拔组件

- **日期**: 2026-04-14
- **我的最新回答**: …
- **参考要点**:
  - …
- **推荐答题**: （一段完整口播，见撰写规则）
- **掌握度**: 良好 / 需复习 / —
- **备注**: …
```

3. Set top metadata: `> Last consolidated: YYYY-MM-DD` and optional session note one line.
4. Save path: **only** `references/SESSION_LOG.md` (do not duplicate into README).

---

## Phase 4 — Output to user

Always print:

1. **本次已归档** 题号列表  
2. **薄弱题号**（掌握度为需复习 / 空白且用户自评为弱）  
3. **与 project-review 对齐建议**：下一题来自 `review_progress.md` 若有  
4. **与 project-learner 对齐建议**：若用户复习了 Dx.y，提示更新 `LEARNING_PROGRESS.md` 是否由 user 手动确认（本 skill **默认不自动改** LEARNING_PROGRESS，除非用户明确说 "同步 learner 进度")

---

## Key paths

| Path | Role |
|------|------|
| `references/SESSION_LOG.md` | Rolling per-question latest answers + refs |
| `references/SESSION_LOG_TEMPLATE.md` | Empty structure / reset |
| `../project-review/references/question_bank.md` | Canonical参考答案要点 |
| `../project-review/review_progress.md` | 章节进度 |
| `../project-learner/references/LEARNING_PROGRESS.md` | 45 知识点进度 |

---

## Question ID conventions

- `project-review`: `1-01` … `9-05` (see question_bank section headers).
- `project-learner`: `D1.1` … `D10.4` — store under `## project-learner 知识点` in same SESSION_LOG.

---

## Anti-patterns

- Do not paste full `question_bank.md` into the log; **summarize** in 参考要点; **推荐答题** must still read as a coherent paragraph (not a raw paste).  
- Do not delete unrelated question blocks when updating one ID.  
- If user answer contains secrets, redact before persisting.
- Do not omit **推荐答题** when creating or refreshing a question block unless user explicitly asks for "仅要点".
