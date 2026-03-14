#!/usr/bin/env python3
"""
文章质量自动评分系统
评估生成文章的质量，低于阈值需要修改
"""

import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent

# 评分阈值
THRESHOLD_PASS = 70
THRESHOLD_EXCELLENT = 85


def load_quality_rules():
    """加载质量评分规则"""
    try:
        import yaml
        config_path = SKILL_DIR / "config" / "quality_rules.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (ImportError, FileNotFoundError):
        # 使用内置默认规则
        return None


def contains_any(text, keywords):
    """检查文本是否包含任一关键词"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def check_practicality(content):
    """实用性（30分）"""
    score = 0
    details = []

    # 有代码示例（15分）
    if "```" in content or "code" in content.lower() or "python" in content.lower():
        score += 15
        details.append("有代码示例 (+15)")
    else:
        details.append("缺少代码示例 (0)")

    # 有具体步骤（10分）
    step_keywords = ["步骤", "第一步", "第二步", "首先", "然后", "接着", "最后",
                     "step 1", "step 2"]
    if contains_any(content, step_keywords):
        score += 10
        details.append("有具体步骤 (+10)")
    else:
        details.append("缺少具体步骤 (0)")

    # 有实际案例（5分）
    case_keywords = ["案例", "例如", "比如", "实例", "example", "for instance", "场景"]
    if contains_any(content, case_keywords):
        score += 5
        details.append("有实际案例 (+5)")
    else:
        details.append("缺少实际案例 (0)")

    return score, details


def check_depth(content):
    """深度（25分）"""
    score = 0
    details = []

    # 字数（10分）
    char_count = len(content)
    if char_count >= 2000:
        score += 10
        details.append(f"字数充足 {char_count}字 (+10)")
    else:
        details.append(f"字数不足 {char_count}字 < 2000字 (0)")

    # 技术细节（10分）
    tech_keywords = ["原理", "机制", "算法", "架构", "实现", "architecture",
                     "mechanism", "API", "参数", "配置"]
    if contains_any(content, tech_keywords):
        score += 10
        details.append("有技术细节 (+10)")
    else:
        details.append("缺少技术细节 (0)")

    # 对比分析（5分）
    compare_keywords = ["对比", "相比", "区别", "优势", "缺点", "vs", "compared to",
                        "不同", "优于"]
    if contains_any(content, compare_keywords):
        score += 5
        details.append("有对比分析 (+5)")
    else:
        details.append("缺少对比分析 (0)")

    return score, details


def check_structure(content):
    """结构完整性（20分）"""
    score = 0
    details = []

    lines = content.split("\n")

    # 有引言（5分）
    first_para = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            first_para.append(stripped)
            if len(" ".join(first_para)) >= 50:
                break
    if len(" ".join(first_para)) >= 50:
        score += 5
        details.append("有引言 (+5)")
    else:
        details.append("缺少引言 (0)")

    # 小标题数量（10分）
    heading_count = len(re.findall(r"^#{2,3}\s", content, re.MULTILINE))
    if heading_count >= 3:
        score += 10
        details.append(f"小标题{heading_count}个 (+10)")
    else:
        details.append(f"小标题{heading_count}个 < 3个 (0)")

    # 有总结（5分）
    summary_keywords = ["总结", "结论", "最后", "综上", "conclusion", "summary",
                        "写在最后"]
    if contains_any(content, summary_keywords):
        score += 5
        details.append("有总结 (+5)")
    else:
        details.append("缺少总结 (0)")

    return score, details


def check_readability(content):
    """可读性（15分）"""
    score = 0
    details = []

    # 段落长度适中（10分）
    paragraphs = [
        p.strip()
        for p in content.split("\n\n")
        if p.strip() and not p.strip().startswith("#")
    ]
    if paragraphs:
        avg_len = sum(len(p) for p in paragraphs) / len(paragraphs)
        if avg_len <= 200:
            score += 10
            details.append(f"段落适中 平均{int(avg_len)}字 (+10)")
        else:
            details.append(f"段落偏长 平均{int(avg_len)}字 > 200字 (0)")
    else:
        details.append("无法检测段落 (0)")

    # 有列表/表格（5分）
    list_keywords = ["- ", "* ", "1. ", "2. ", "|"]
    if contains_any(content, list_keywords):
        score += 5
        details.append("有列表/表格 (+5)")
    else:
        details.append("缺少列表/表格 (0)")

    return score, details


def check_originality(content):
    """原创性（10分）"""
    score = 0
    details = []

    # 非简单翻译（5分）
    translation_keywords = ["根据原文", "原文指出", "according to", "translated from"]
    if not contains_any(content, translation_keywords):
        score += 5
        details.append("非简单翻译 (+5)")
    else:
        details.append("疑似翻译内容 (0)")

    # 有独特见解（5分）
    insight_keywords = ["我认为", "值得注意", "关键在于", "建议", "推荐", "需要注意"]
    if contains_any(content, insight_keywords):
        score += 5
        details.append("有独特见解 (+5)")
    else:
        details.append("缺少独特见解 (0)")

    return score, details


def check_penalties(content):
    """扣分项"""
    penalty = 0
    details = []

    # 大量空话
    filler_keywords = ["随着AI的发展", "在当今时代", "众所周知", "不言而喻"]
    count = sum(1 for kw in filler_keywords if kw in content)
    if count > 2:
        penalty -= 5
        details.append(f"空话过多 {count}处 (-5)")

    return penalty, details


def check_article(article_path):
    """检查文章质量，返回 (score, details, passed)"""
    with open(article_path, "r", encoding="utf-8") as f:
        content = f.read()

    all_details = []
    total = 0

    checks = [
        ("实用性", check_practicality),
        ("深度", check_depth),
        ("结构", check_structure),
        ("可读性", check_readability),
        ("原创性", check_originality),
    ]

    for name, check_fn in checks:
        score, details = check_fn(content)
        total += score
        all_details.append(f"\n【{name}】")
        all_details.extend(f"  {d}" for d in details)

    # 扣分
    penalty, pen_details = check_penalties(content)
    total += penalty
    if pen_details:
        all_details.append("\n【扣分项】")
        all_details.extend(f"  {d}" for d in pen_details)

    total = max(0, min(100, total))
    passed = total >= THRESHOLD_PASS

    return total, all_details, passed


def main():
    if len(sys.argv) < 2:
        print("用法: check_quality.py <文章路径>")
        sys.exit(1)

    article_path = sys.argv[1]
    if not os.path.exists(article_path):
        print(f"文章文件不存在: {article_path}")
        sys.exit(1)

    print(f"\n正在检查文章质量: {os.path.basename(article_path)}")
    print("=" * 50)

    total, details, passed = check_article(article_path)

    for d in details:
        print(d)

    print("\n" + "=" * 50)
    print(f"\n总分: {total}/100")

    if total >= THRESHOLD_EXCELLENT:
        print("质量评级: 优秀")
    elif total >= THRESHOLD_PASS:
        print("质量评级: 合格")
    else:
        print("质量评级: 不合格（需要修改）")

    print("=" * 50)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
