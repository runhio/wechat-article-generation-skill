# wechat-article-generation-skill

> 一句话让 Claude Code 帮你写公众号文章，自动发布到草稿箱。

全自动 AI 文章生成 + 微信公众号发布的 [Claude Code](https://claude.ai/claude-code) Skill。基于微信官方 API，无需第三方服务。

## 功能特性

**双模式运行**
- **自动模式**：Claude Code 自动搜索 AI 热点 → 语义去重 → 撰写文章 → 发布
- **手动模式**：你给话题，Claude Code 帮你写 → 发布

**智能写作**
- 自动搜索资料，2000-3000 字高质量中文文章
- 5 维度质量评分（实用性/深度/结构/可读性/原创性），≥70 分才发布
- 语义去重，与最近 48 小时已发布内容对比，不重复写同一话题

**一键发布**
- Markdown → 带样式 HTML 自动转换（AI Tech 紫蓝主题）
- 封面图自动上传
- 通过微信官方 API 直接发布到草稿箱

## 效果预览

文章样式特点：
- H2 标题带紫色左边框 + 淡紫背景
- 代码块 Atom One Dark 深色主题
- 行内代码粉色高亮
- 表格紫色表头 + 斑马纹
- 引用块紫色左边框

## 快速开始

### 1. 配置微信公众号

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 AppID 和 AppSecret：

```env
WECHAT_APPID=wx你的appid
WECHAT_SECRET=你的appsecret
```

从 [微信公众平台](https://mp.weixin.qq.com) → 设置与开发 → 基本配置 获取。

### 2. IP 白名单

将你机器的公网 IP 添加到微信公众平台白名单：

```bash
curl -s ifconfig.me
```

微信公众平台 → 设置与开发 → 基本配置 → IP白名单

> 注意：如果使用 VPN，实际出口 IP 可能不同。脚本报错时会打印微信返回的真实 IP。

### 3. 安装 Skill

```bash
cp -r skills/wechat-article-generation ~/.claude/skills/
cp .env ~/.claude/skills/wechat-article-generation/.env
```

### 4. 使用

在 Claude Code 中新开对话：

```
# 自动模式：搜索 AI 热点并写文章
帮我生成今天的AI文章

# 手动模式：指定话题
写一篇关于 Claude Code 的公众号文章
```

## 工作流

```
自动模式: Claude搜索AI热点 → 语义去重 → 撰写文章 → 质量检查 → 发布到草稿箱
手动模式: 用户给话题 ────────────────→ 撰写文章 → 质量检查 → 发布到草稿箱
```

## 项目结构

```
skills/wechat-article-generation/
├── SKILL.md                    # Skill 定义（Claude Code 读取）
├── scripts/
│   ├── select_topic.py         # 发布历史管理（记录/查询，用于语义去重）
│   ├── check_quality.py        # 文章质量自动评分（5 维度，满分 100）
│   └── wechat_api.py           # 微信官方 API + Markdown→HTML 转换 + 封面图上传
├── assets/
│   └── default_cover.png       # 默认封面图
├── config/
│   └── quality_rules.yaml      # 质量评分规则
└── cache/                      # 运行时缓存（.gitignore）
```

## 技术实现

| 模块 | 说明 |
|------|------|
| 热点搜索 | Claude Code 通过 WebSearch 搜索，无 RSS 依赖 |
| 去重 | 语义级别，Claude Code 对比历史摘要判断是否同一事件 |
| 写作 | Claude Code 自身完成，按 SKILL.md 中定义的结构和风格规范 |
| 质量检查 | Python 脚本，5 维度关键词检测，满分 100 |
| HTML 转换 | Python 脚本，Markdown → inline style HTML，AI Tech 紫蓝主题 |
| 发布 | 微信官方 API（`api.weixin.qq.com`），access_token 自动缓存 |

## 前置要求

- [Claude Code](https://claude.ai/claude-code)
- Python 3.9+
- 微信公众号（已认证或未认证均可，需开启开发者模式）

## 许可证

MIT
