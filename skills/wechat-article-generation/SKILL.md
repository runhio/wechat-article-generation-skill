---
name: wechat-article-generation
description: Auto-generate high-quality Chinese AI articles and publish to WeChat Official Account drafts. Supports two modes - auto mode (search AI hotspots and pick topic automatically) and manual mode (user provides topic). Trigger when user says "generate article", "write today's post", "auto publish", "AI hot topic article", or provides a specific topic to write about.
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Edit
---

# WeChat AI Article Auto-Generation System

Two operating modes:
- **Auto mode**: Search AI hotspots → Deduplicate → Write article → Quality check → Publish to drafts
- **Manual mode**: User provides topic → Write article → Quality check → Publish to drafts

## Prerequisites

- WeChat Official Account with AppID + AppSecret (from https://mp.weixin.qq.com)
- Run `python3 scripts/wechat_api.py setup` to configure (first time only)
- Server IP must be added to WeChat IP whitelist
- Python 3.9+

## Trigger Conditions

**Auto mode** — user says something like:
- "帮我生成今天的AI文章"
- "写今天的公众号内容"
- "自动生成并发布"

**Manual mode** — user provides a specific topic:
- "写一篇关于 Claude Code 的文章"
- "帮我写一篇 LangChain 入门教程发到公众号"
- "把这个话题写成公众号文章：{topic}"

---

## Workflow: Auto Mode

### Step 1: Check publish history

```bash
cd <skill_dir>
python3 scripts/select_topic.py --show-history
```

Review articles published in the last 48 hours (titles + summaries) to avoid duplicates.

### Step 2: Search AI hotspots and pick candidates (you do this)

Use WebSearch to find latest AI news, 3-5 search rounds:

1. **Latest news**: search "AI news today", "AI 最新消息", "AI new release 2026"
2. **Trending projects**: search "GitHub trending AI projects", "new AI tools"
3. **Breakthroughs**: search "AI research breakthrough", "大模型 最新进展"
4. **Follow-up**: dig deeper based on earlier findings

Pick 3-5 valuable candidates. Requirements:
- Must be AI-related (LLMs, AI tools, ML, etc.)
- Exclude pure business news (funding, layoffs, M&A)
- Prefer: new tool releases, practical tutorials, technical breakthroughs
- Prefer: content with concrete value (something developers can use or learn)

### Step 3: Semantic deduplication (you do this)

Compare candidates against publish history from Step 1:

- If a candidate covers the **same product/event/technology** as a published article, even with completely different wording, it counts as duplicate — skip it
- Pick the first non-duplicate candidate as the final topic
- If all candidates are duplicates, inform user and stop

Save the selected topic (title, source URL, brief description) to `cache/selected_topic.json`.

Then proceed to **Step 4: Write article** below.

---

## Workflow: Manual Mode

When user provides a specific topic, skip Steps 1-3 entirely.

Save the user-provided topic to `cache/selected_topic.json`, then proceed to **Step 4: Write article** below.

---

## Step 4: Write the article (you do this)

Read `cache/selected_topic.json` and write the article.

**You are the writer.** Use WebSearch and WebFetch to research, then write in your own words.

### Research strategy (3-5 rounds)

1. **Official sources**: search "{product} official docs", "{product} official blog"
2. **Technical analysis**: search "{product} tutorial", "{product} 教程"
3. **Comparisons**: search "{product} vs {competitor}", "{product} review"
4. **Verification**: fill in gaps from earlier rounds

### Article structure (2000-3000 Chinese characters)

```
# Article Title

Hook (100-200 chars)
→ Open with a scenario or question to grab attention

## What is it (300-500 chars)
→ Basic introduction of the product/technology
→ Use analogies to explain core concepts

## What can it do (500-800 chars)
→ Core features and capabilities
→ Real-world use cases and examples

## Why it matters (300-500 chars)
→ Unique advantages
→ Comparison with alternatives

## How to get started (200-300 chars)
→ Quick start guide
→ Official resource links

## Summary (100-200 chars)
→ Key takeaways and outlook
```

### Writing rules

**Language & style:**
- Simplified Chinese
- Use "我们", "你" (second person) for a friendly tone
- Keep sentences short (≤25 chars)
- Use subheadings, lists, and parallel structures
- Rewrite in your own words — never copy source text
- Explain technical terms for general readers

**Title requirements:**
- Length: 15-30 chars (≤64 bytes)
- Include specific numbers ("3 tips", "5 steps")
- Highlight direct benefits
- Be specific, not vague
- No clickbait ("震惊！", "必看！")

**Format requirements:**
- Plain text links only: `Official site: https://example.com/`
- Do NOT use markdown hyperlinks `[text](url)`
- Output only: title + body + summary
- Do NOT add "References", "Image credits" or similar sections
- Output format must be Markdown (.md)

### Output

Save the article as: `cache/article.md`

### Step 4b: Quality check

```bash
python3 scripts/check_quality.py cache/article.md
```

Scoring dimensions (100 points total):
- Practicality (30): code examples, concrete steps, real cases
- Depth (25): word count ≥2000, technical details, comparisons
- Structure (20): has intro, ≥3 subheadings, has summary
- Readability (15): moderate paragraph length, lists/tables
- Originality (10): not a simple translation, has unique insights

**≥70**: Pass — proceed to publish
**<70**: Fail — revise the article based on the checker output, then re-check (max 2 retries)

---

## Step 5: Publish to WeChat drafts

### 5.1 Check config

```bash
python3 scripts/wechat_api.py check-env
```

If not configured, run setup first:

```bash
python3 scripts/wechat_api.py setup
```

This will prompt for AppID and AppSecret (from https://mp.weixin.qq.com → 设置与开发 → 基本配置). Config is saved to `~/.wechat-publisher/config.json`.

### 5.2 Publish

```bash
python3 scripts/wechat_api.py publish \
  --markdown cache/article.md \
  --author "硅基茶室"
```

Parameters:
- `--markdown`: Markdown file path (required)
- `--title`: Custom title (defaults to H1 from file)
- `--summary`: Summary (defaults to first paragraph, ≤120 chars)
- `--author`: Author name

The script automatically converts Markdown to WeChat-compatible HTML and creates a draft via the official WeChat API.

---

## Step 6: Record publish history

After successful publish:

```bash
python3 scripts/select_topic.py --record-history \
  --title "Article title" \
  --summary "1-2 sentence summary of what the article covers" \
  --url "source URL" \
  --content-type "new_tool"
```

**The `--summary` is critical**: it gets stored in `cache/publish_history.json` and is used for semantic deduplication next time. Write 1-2 sentences that accurately capture the core content (product name, event, key technical points). Do NOT just copy the title.

---

## Step 7: Final summary

```
✅ Article generation complete

Time: {current_time}
Content type: {type}

【WeChat Official Account】
Title: {article_title}
Word count: {count} chars
Quality score: {score}/100
Status: Published to drafts

Review the draft at:
https://mp.weixin.qq.com
```

---

## Scripts

All scripts are in `scripts/`:

| Script | Purpose |
|--------|---------|
| `select_topic.py` | Publish history management (record/query, for semantic dedup) |
| `check_quality.py` | Article quality scoring |
| `wechat_api.py` | WeChat API client (publish to drafts) |

## Config

| File | Purpose |
|------|---------|
| `config/quality_rules.yaml` | Quality scoring rules |

## Cache

```
cache/
├── selected_topic.json    # Selected topic
├── article.md             # Generated article
└── publish_history.json   # Publish history (with summaries, for semantic dedup)
```

## Important Rules

1. **Draft only**: Never auto-publish. User must manually review and publish.
2. **Quality first**: Do not publish if quality score < 70.
3. **Semantic dedup**: Compare against last 48h of published content. Same product/event/technology = duplicate.
4. **AI-related only**: Only select AI-related topics (in auto mode).
