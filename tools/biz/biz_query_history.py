#!/usr/bin/env python3
"""
Business Analyst - 查询历史商业分析数据

从 data/business_reports/ 读取历史分析报告

Usage:
    python tools/biz/biz_query_history.py --last_n 4
    python tools/biz/biz_query_history.py --industry seafood_restaurant --last_n 8
    python tools/biz/biz_query_history.py --keyword "帝王蟹"
    python tools/biz/biz_query_history.py --period 2026-W08
"""
import argparse
import json
import sys
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent.parent / "data" / "business_reports"


def load_reports(industry=None):
    """加载所有报告，可选按行业过滤"""
    reports = []

    if not DATA_DIR.exists():
        return reports

    if industry:
        search_dirs = [DATA_DIR / industry]
    else:
        search_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir()]

    for d in search_dirs:
        if not d.exists():
            continue
        for f in d.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    report = json.load(fp)
                    report['_file'] = str(f)
                    reports.append(report)
            except (json.JSONDecodeError, IOError):
                continue

    # 按 period_end 降序排列（最近的在前）
    reports.sort(key=lambda r: r.get('period_end', ''), reverse=True)
    return reports


def search_reports(reports, keyword):
    """在报告内容中搜索关键词"""
    matched = []
    keyword_lower = keyword.lower()

    for r in reports:
        searchable = json.dumps(r, ensure_ascii=False).lower()
        if keyword_lower in searchable:
            matched.append(r)

    return matched


def main():
    parser = argparse.ArgumentParser(description='查询历史商业分析数据')
    parser.add_argument('--last_n', type=int, default=4, help='返回最近 N 条记录，默认 4')
    parser.add_argument('--industry', default=None, help='按行业过滤')
    parser.add_argument('--keyword', default=None, help='搜索关键词')
    parser.add_argument('--period', default=None, help='查询特定周期，如 2026-W08')

    args = parser.parse_args()

    # 加载报告
    reports = load_reports(industry=args.industry)

    if not reports:
        if args.industry:
            print(f"📭 暂无 {args.industry} 的历史数据")
        else:
            print("📭 暂无历史数据")
        sys.exit(0)

    # 按周期过滤
    if args.period:
        reports = [r for r in reports if args.period in r.get('_file', '')]

    # 按关键词搜索
    if args.keyword:
        reports = search_reports(reports, args.keyword)
        if not reports:
            print(f"🔍 未找到包含 \"{args.keyword}\" 的记录")
            sys.exit(0)

    # 限制数量
    reports = reports[:args.last_n]

    # 输出（去掉内部字段）
    output = []
    for r in reports:
        clean = {k: v for k, v in r.items() if not k.startswith('_')}
        output.append(clean)

    print(f"📊 找到 {len(output)} 条记录\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
