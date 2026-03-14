#!/usr/bin/env python3
"""
发布历史管理脚本
记录和查询已发布文章，供 Claude Code 做语义去重判断。

用法:
    # 查看最近48小时发布历史
    python select_topic.py --show-history

    # 记录一条发布历史
    python select_topic.py --record-history \
        --title "文章标题" \
        --summary "文章核心内容摘要" \
        --url "原始URL" \
        --content-type "new_tool"
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
CACHE_DIR = SKILL_DIR / "cache"


def load_history(hours=48):
    """加载最近 N 小时的发布历史"""
    history_file = CACHE_DIR / "publish_history.json"
    if not history_file.exists():
        return []

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        cutoff = time.time() - (hours * 3600)
        return [r for r in data.get("records", []) if r.get("timestamp", 0) > cutoff]
    except Exception:
        return []


def save_history_record(title, summary="", url="", content_type="unknown"):
    """保存一条发布记录"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    history_file = CACHE_DIR / "publish_history.json"

    data = {"records": []}
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data["records"].append({
        "title": title,
        "summary": summary,
        "url": url,
        "content_type": content_type,
        "timestamp": time.time(),
        "date": datetime.now().isoformat(),
    })

    # 只保留最近7天的记录
    cutoff = time.time() - (7 * 24 * 3600)
    data["records"] = [r for r in data["records"] if r.get("timestamp", 0) > cutoff]

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已记录发布历史: {title}")


def show_history(hours=48):
    """显示最近的发布历史"""
    history = load_history(hours=hours)

    if not history:
        print(f"最近{hours}小时无发布记录。")
        return

    print(f"最近{hours}小时已发布文章（{len(history)}篇）：")
    print("=" * 50)
    for i, record in enumerate(history, 1):
        print(f"\n[{i}] {record.get('title', '无标题')}")
        if record.get("summary"):
            print(f"    摘要: {record['summary']}")
        if record.get("url"):
            print(f"    来源: {record['url']}")
        print(f"    类型: {record.get('content_type', '未知')}")
        print(f"    时间: {record.get('date', '未知')[:16]}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="发布历史管理")

    parser.add_argument("--show-history", action="store_true",
                        help="显示最近发布历史")
    parser.add_argument("--hours", type=int, default=48,
                        help="查看最近N小时的历史（默认48）")
    parser.add_argument("--record-history", action="store_true",
                        help="记录一条发布历史")
    parser.add_argument("--title", help="文章标题")
    parser.add_argument("--summary", help="文章摘要（1-2句话概括核心内容）")
    parser.add_argument("--url", help="原始来源URL")
    parser.add_argument("--content-type", help="内容类型（new_tool/tutorial/industry_news）")

    args = parser.parse_args()

    if args.record_history:
        if not args.title:
            print("记录历史需要 --title 参数", file=sys.stderr)
            sys.exit(1)
        save_history_record(
            title=args.title,
            summary=args.summary or "",
            url=args.url or "",
            content_type=args.content_type or "unknown",
        )
    elif args.show_history:
        show_history(hours=args.hours)
    else:
        # 默认显示历史
        show_history(hours=args.hours)


if __name__ == "__main__":
    main()
