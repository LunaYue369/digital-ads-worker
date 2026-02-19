#!/usr/bin/env python3
"""
Business Analyst - 保存商业分析摘要到本地 JSON

将 clawdbot 的分析结果保存到 data/business_reports/{industry}/YYYY-W##.json

Usage:
    python tools/biz_save_summary.py \
        --industry seafood_restaurant \
        --period_start 2026-02-11 \
        --period_end 2026-02-18 \
        --summary "春节期间营业额平均增长35%..." \
        --kpis '{"total_revenue": 199500, ...}' \
        --trends "高端海鲜需求激增" \
        --recommendations '["减少帝王蟹备货30%", "推出春季套餐"]'
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data" / "business_reports"


def main():
    parser = argparse.ArgumentParser(description='保存商业分析摘要')
    parser.add_argument('--industry', required=True, help='行业标识，如 seafood_restaurant')
    parser.add_argument('--period_start', required=True, help='周期开始日期 YYYY-MM-DD')
    parser.add_argument('--period_end', required=True, help='周期结束日期 YYYY-MM-DD')
    parser.add_argument('--summary', required=True, help='整体分析总结')
    parser.add_argument('--kpis', required=True, help='关键指标 JSON 字符串')
    parser.add_argument('--trends', default='', help='趋势分析')
    parser.add_argument('--recommendations', default='[]', help='建议列表 JSON 数组')

    args = parser.parse_args()

    # 解析 JSON 字段
    try:
        kpis = json.loads(args.kpis)
    except json.JSONDecodeError as e:
        print(f"❌ KPIs JSON 解析失败: {e}")
        sys.exit(1)

    try:
        recommendations = json.loads(args.recommendations)
    except json.JSONDecodeError as e:
        print(f"❌ Recommendations JSON 解析失败: {e}")
        sys.exit(1)

    # 计算 ISO 周号作为文件名
    try:
        end_date = datetime.strptime(args.period_end, '%Y-%m-%d')
        iso_year, iso_week, _ = end_date.isocalendar()
        filename = f"{iso_year}-W{iso_week:02d}.json"
    except ValueError:
        # 如果日期格式不标准，用 period_end 作为文件名
        filename = f"{args.period_end}.json"

    # 构建报告
    report = {
        "industry": args.industry,
        "period": f"{args.period_start} ~ {args.period_end}",
        "period_start": args.period_start,
        "period_end": args.period_end,
        "summary": args.summary,
        "kpis": kpis,
        "trends": args.trends,
        "recommendations": recommendations,
        "saved_at": datetime.now().isoformat()
    }

    # 保存到文件
    industry_dir = DATA_DIR / args.industry
    industry_dir.mkdir(parents=True, exist_ok=True)

    output_path = industry_dir / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✅ 分析摘要已保存")
    print(f"📁 路径: {output_path}")
    print(f"📅 周期: {report['period']}")
    print(f"🏭 行业: {args.industry}")
    print(f"📊 KPI 数量: {len(kpis)} 项")
    print(f"💡 建议数量: {len(recommendations)} 条")


if __name__ == '__main__':
    main()
