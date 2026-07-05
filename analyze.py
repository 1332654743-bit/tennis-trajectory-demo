#!/usr/bin/env python3
"""
运动分享调研数据分析脚本

用法:
  python analyze.py --url https://your-app.vercel.app/api/results
  python analyze.py --dir ./data_files/
  python analyze.py --file tracker-xxx.json tracker-yyy.json

输出: 终端表格 + report.md 文件
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from statistics import median, mean

# ========== 数据加载 ==========

def load_from_url(url):
    import urllib.request
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data['submissions']

def load_from_dir(dirpath):
    submissions = []
    for fname in sorted(os.listdir(dirpath)):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        # 支持两种格式: 直接 {events, summary} 或包装后的 {userId, data: {events, summary}}
        if 'data' in raw and 'events' in raw['data']:
            submissions.append(raw)
        elif 'events' in raw:
            submissions.append({'userId': fname, 'data': raw, 'submittedAt': ''})
    return submissions

def load_from_files(filepaths):
    submissions = []
    for fpath in filepaths:
        with open(fpath, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, list):
            for item in raw:
                sub = normalize_item(item)
                if sub:
                    submissions.append(sub)
        else:
            sub = normalize_item(raw)
            if sub:
                submissions.append(sub)
            else:
                submissions.append({'userId': os.path.basename(fpath), 'data': raw, 'submittedAt': ''})
    return submissions


def normalize_item(raw):
    if raw.get('data') and raw['data'].get('summary'):
        return raw
    if raw.get('userId') and raw.get('events') and raw.get('summary'):
        return {'userId': raw['userId'], 'data': {'events': raw['events'], 'summary': raw['summary']}, 'submittedAt': raw.get('submittedAt', '')}
    if raw.get('events') and raw.get('summary'):
        return {'userId': raw.get('userId', 'unknown'), 'data': raw, 'submittedAt': ''}
    return None

# ========== 数据质量过滤 ==========

CARELESS_MAX_DURATION_MS = 120000  # 敷衍判定：总时长 < 120秒
CARELESS_MAX_NON_DEFAULT = 2  # 敷衍判定：非默认操作 ≤ 2个
MANDATORY_FEATURES = {'style-watermark', 'style-video', 'style-report', 'template-select', 'bg-confirm'}
STYLE_ORDER_SEQ = ['watermark', 'video', 'report']

def get_total_duration(sub):
    summary = sub.get('data', {}).get('summary', {})
    return sum(info.get('totalDuration', 0) for info in summary.values())

def is_careless(sub):
    """判定敷衍作答：同时满足 按顺序点 + 总时长<120s + 非默认操作≤2"""
    summary = sub.get('data', {}).get('summary', {})
    events = sub.get('data', {}).get('events', [])
    scenarios = ['daily', 'pb', 'marathon']
    # 条件1：样式选择完全按按钮顺序
    scenario_first_ts = {}
    for e in events:
        s = e.get('scenario', '')
        if s in scenarios and s not in scenario_first_ts:
            scenario_first_ts[s] = e.get('timestamp', 0)
    if len(scenario_first_ts) < 3:
        return False
    ordered = sorted(scenario_first_ts.keys(), key=lambda x: scenario_first_ts[x])
    choices = [summary.get(s, {}).get('styleChoice', '') for s in ordered]
    if choices != STYLE_ORDER_SEQ:
        return False
    # 条件2：总时长 < 120秒
    if get_total_duration(sub) >= CARELESS_MAX_DURATION_MS:
        return False
    # 条件3：非默认操作 ≤ 2个
    all_features = set()
    for s in scenarios:
        all_features.update(summary.get(s, {}).get('featuresUsed', []))
    non_default = all_features - MANDATORY_FEATURES
    return len(non_default) <= CARELESS_MAX_NON_DEFAULT

def filter_valid_submissions(submissions):
    valid, careless = [], []
    for sub in submissions:
        if is_careless(sub):
            careless.append(sub)
        else:
            valid.append(sub)
    return valid, careless

# ========== 分析核心 ==========

SCENARIO_NAMES = {'daily': '日常打卡', 'pb': '成绩突破', 'marathon': '马拉松完赛'}
STYLE_NAMES = {'watermark': '水印海报', 'video': '轨迹视频', 'report': '运动报告'}
# 基于10人深度访谈加权分享行为占比（排除D社交玩法7%后归一化）
# A存在打卡61%→日常, B数据炫耀17%→PB, C体验叙事15%→马拉松
WEIGHTS = {'daily': 0.656, 'pb': 0.183, 'marathon': 0.161}

def analyze_q1(submissions):
    """Q1: 各场景下用户更倾向哪类分享样式"""
    matrix = {s: Counter() for s in ['daily', 'pb', 'marathon']}

    for sub in submissions:
        summary = sub.get('data', {}).get('summary', {})
        for scenario, info in summary.items():
            if scenario in matrix:
                style = info.get('styleChoice', 'unknown')
                matrix[scenario][style] += 1

    return matrix

def analyze_q2(submissions):
    """Q2: 用户是否愿意编辑 + 花多久"""
    durations = defaultdict(list)
    feature_counts = defaultdict(list)
    abandon_count = defaultdict(int)
    total_per_scenario = defaultdict(int)

    for sub in submissions:
        summary = sub.get('data', {}).get('summary', {})
        for scenario, info in summary.items():
            if scenario not in SCENARIO_NAMES:
                continue
            total_per_scenario[scenario] += 1
            durations[scenario].append(info.get('totalDuration', 0))
            feature_counts[scenario].append(info.get('featureCount', 0))
            if info.get('abandoned'):
                abandon_count[scenario] += 1

    result = {}
    for s in ['daily', 'pb', 'marathon']:
        arr = sorted(durations[s]) if durations[s] else [0]
        fc = feature_counts[s] if feature_counts[s] else [0]
        total = total_per_scenario[s] or 1
        zero_edit = sum(1 for c in fc if c <= 1)  # 只选了样式没做其他操作
        result[s] = {
            'median_ms': median(arr),
            'mean_ms': mean(arr),
            'p25_ms': arr[len(arr)//4] if len(arr) >= 4 else arr[0],
            'p75_ms': arr[3*len(arr)//4] if len(arr) >= 4 else arr[-1],
            'zero_edit_rate': zero_edit / total,
            'abandon_rate': abandon_count[s] / total,
            'n': total
        }
    return result

def analyze_q3(submissions):
    """Q3: 用户真实优先使用哪些功能"""
    feature_users = Counter()  # 多少人用了该功能
    feature_order = defaultdict(list)  # 该功能在各人操作序列中的排位

    total_users = len(submissions)

    for sub in submissions:
        summary = sub.get('data', {}).get('summary', {})
        seen = set()
        for scenario in ['daily', 'pb', 'marathon']:
            info = summary.get(scenario, {})
            features = info.get('featuresUsed', [])
            for i, feat in enumerate(features):
                if feat.startswith('style-'):
                    continue  # 排除样式选择本身
                if feat not in seen:
                    feature_users[feat] += 1
                    seen.add(feat)
                feature_order[feat].append(i)

    result = []
    for feat, count in feature_users.most_common(20):
        orders = feature_order[feat]
        result.append({
            'feature': feat,
            'users': count,
            'usage_rate': count / total_users if total_users else 0,
            'avg_order': mean(orders) if orders else 99,
        })
    return result


def get_scenario_order(sub):
    """根据事件时间戳推断用户的场景完成顺序，返回 ['daily','pb','marathon'] 的排列"""
    events = sub.get('data', {}).get('events', [])
    first_ts = {}
    for e in events:
        s = e.get('scenario')
        if s and s not in first_ts:
            first_ts[s] = e.get('timestamp', 0)
    return sorted(first_ts.keys(), key=lambda s: first_ts[s])


def analyze_learning_effect(submissions):
    """学习效应分析：对比第1个场景（探索期）vs 第2-3个场景（熟悉期）"""
    first_features = Counter()
    later_features = Counter()
    first_durations = []
    later_durations = []
    first_count = 0
    later_count = 0

    for sub in submissions:
        order = get_scenario_order(sub)
        summary = sub.get('data', {}).get('summary', {})
        if len(order) < 2:
            continue

        for idx, scenario in enumerate(order):
            info = summary.get(scenario, {})
            if not info:
                continue
            features = info.get('featuresUsed', [])
            duration = info.get('totalDuration', 0)

            if idx == 0:
                first_count += 1
                first_durations.append(duration)
                for f in features:
                    if not f.startswith('style-'):
                        first_features[f] += 1
            else:
                later_count += 1
                later_durations.append(duration)
                for f in features:
                    if not f.startswith('style-'):
                        later_features[f] += 1

    # 功能使用率对比
    all_features = set(list(first_features.keys()) + list(later_features.keys()))
    feature_comparison = []
    for f in all_features:
        first_rate = first_features[f] / first_count if first_count else 0
        later_rate = later_features[f] / later_count if later_count else 0
        diff = first_rate - later_rate
        feature_comparison.append({
            'feature': f,
            'first_rate': first_rate,
            'later_rate': later_rate,
            'diff': diff,  # 正值=可能是探索性点击
        })
    feature_comparison.sort(key=lambda x: -abs(x['diff']))

    return {
        'first_median_ms': median(sorted(first_durations)) if first_durations else 0,
        'later_median_ms': median(sorted(later_durations)) if later_durations else 0,
        'first_count': first_count,
        'later_count': later_count,
        'feature_comparison': feature_comparison[:10],
    }

def weighted_style(q1_matrix):
    """加权合并样式选择"""
    styles = ['watermark', 'video', 'report']
    weighted = Counter()
    total_weight = 0
    for scenario, counter in q1_matrix.items():
        w = WEIGHTS.get(scenario, 0)
        scenario_total = sum(counter.values()) or 1
        for style in styles:
            weighted[style] += w * (counter.get(style, 0) / scenario_total)
        total_weight += w
    # Normalize
    result = {}
    for style in styles:
        result[style] = weighted[style] / total_weight if total_weight else 0
    return result

# ========== 报表输出 ==========

def fmt_dur(ms):
    s = round(ms / 1000)
    if s < 60:
        return f"{s}秒"
    return f"{s//60}分{s%60}秒"

def fmt_pct(rate):
    return f"{rate*100:.0f}%"

def generate_report(submissions, invalid_count=0):
    n = len(submissions)
    lines = []
    lines.append(f"# 运动分享调研分析报告\n")
    lines.append(f"**有效样本：{n} 人**（已剔除 {invalid_count} 份无效数据，过滤规则：总操作时长 < 60秒）\n")
    lines.append(f"---\n")

    # Q1
    q1 = analyze_q1(submissions)
    lines.append("## Q1: 各场景下用户更倾向哪类分享样式\n")
    lines.append("| 场景 | 水印海报 | 轨迹视频 | 运动报告 |")
    lines.append("|------|---------|---------|---------|")
    for s in ['daily', 'pb', 'marathon']:
        total = sum(q1[s].values()) or 1
        row = [SCENARIO_NAMES[s]]
        for style in ['watermark', 'video', 'report']:
            count = q1[s].get(style, 0)
            row.append(f"{count}/{total} ({fmt_pct(count/total)})")
        lines.append(f"| {' | '.join(row)} |")

    ws = weighted_style(q1)
    lines.append(f"\n**加权汇总**（日常60%/PB25%/马拉松15%）：海报 {fmt_pct(ws['watermark'])} / 视频 {fmt_pct(ws['video'])} / 报告 {fmt_pct(ws['report'])}\n")
    lines.append("---\n")

    # Q2
    q2 = analyze_q2(submissions)
    lines.append("## Q2: 用户编辑意愿与时长\n")
    lines.append("| 场景 | 中位时长 | 平均时长 | P25 | P75 | 不编辑比例 | 放弃率 |")
    lines.append("|------|---------|---------|-----|-----|-----------|-------|")
    for s in ['daily', 'pb', 'marathon']:
        info = q2[s]
        lines.append(f"| {SCENARIO_NAMES[s]} | {fmt_dur(info['median_ms'])} | {fmt_dur(info['mean_ms'])} | {fmt_dur(info['p25_ms'])} | {fmt_dur(info['p75_ms'])} | {fmt_pct(info['zero_edit_rate'])} | {fmt_pct(info['abandon_rate'])} |")
    lines.append("")
    lines.append("---\n")

    # Q3
    q3 = analyze_q3(submissions)
    lines.append("## Q3: 功能优先级排序\n")
    lines.append("| 排名 | 功能 | 使用率 | 平均操作顺序 | 使用人数 |")
    lines.append("|------|------|--------|------------|---------|")
    for i, item in enumerate(q3[:15], 1):
        lines.append(f"| {i} | {item['feature']} | {fmt_pct(item['usage_rate'])} | {item['avg_order']:.1f} | {item['users']}/{n} |")
    lines.append("")
    lines.append("---\n")

    # Learning Effect
    le = analyze_learning_effect(submissions)
    lines.append("## Q4: 学习效应分析（第1场景 vs 第2-3场景）\n")
    lines.append(f"**编辑时长对比：** 第1场景中位 {fmt_dur(le['first_median_ms'])} → 第2-3场景中位 {fmt_dur(le['later_median_ms'])}\n")
    if le['feature_comparison']:
        lines.append("**功能使用率差异（探索性指标）：**\n")
        lines.append("| 功能 | 第1场景使用率 | 第2-3场景使用率 | 差值 | 判断 |")
        lines.append("|------|-------------|---------------|------|------|")
        for fc in le['feature_comparison']:
            judgment = '可能是探索' if fc['diff'] > 0.15 else ('后期更多' if fc['diff'] < -0.15 else '稳定')
            lines.append(f"| {fc['feature']} | {fmt_pct(fc['first_rate'])} | {fmt_pct(fc['later_rate'])} | {fc['diff']:+.0%} | {judgment} |")
        lines.append("")
    lines.append("---\n")

    # Summary
    lines.append("## 结论摘要\n")
    top_style = max(ws, key=ws.get)
    lines.append(f"- **最受偏好的样式：** {STYLE_NAMES.get(top_style, top_style)}（加权 {fmt_pct(ws[top_style])}）")
    daily_zero = q2['daily']['zero_edit_rate']
    lines.append(f"- **日常场景不编辑比例：** {fmt_pct(daily_zero)}")
    marathon_dur = q2['marathon']['median_ms']
    lines.append(f"- **马拉松场景中位编辑时长：** {fmt_dur(marathon_dur)}")
    if q3:
        lines.append(f"- **最高使用率功能：** {q3[0]['feature']}（{fmt_pct(q3[0]['usage_rate'])}）")
    lines.append("")

    return '\n'.join(lines)

# ========== 主函数 ==========

def main():
    parser = argparse.ArgumentParser(description='运动分享调研数据分析')
    parser.add_argument('--url', help='从线上 /api/results 接口拉取数据')
    parser.add_argument('--dir', help='从本地文件夹读取 JSON 文件')
    parser.add_argument('--file', nargs='+', help='指定一个或多个 JSON 文件')
    parser.add_argument('--output', default='report.md', help='输出报告文件名 (默认 report.md)')
    args = parser.parse_args()

    if args.url:
        print(f"从 {args.url} 拉取数据...")
        submissions = load_from_url(args.url)
    elif args.dir:
        print(f"从 {args.dir} 读取文件...")
        submissions = load_from_dir(args.dir)
    elif args.file:
        print(f"读取 {len(args.file)} 个文件...")
        submissions = load_from_files(args.file)
    else:
        print("请指定数据来源: --url / --dir / --file")
        print("示例: python analyze.py --file tracker-xxx.json")
        sys.exit(1)

    if not submissions:
        print("❌ 未找到有效数据")
        sys.exit(1)

    print(f"✅ 加载 {len(submissions)} 份原始数据")

    # 数据质量过滤：剔除敷衍作答（按顺序点 + <120s + 非默认≤2）
    submissions, careless = filter_valid_submissions(submissions)
    if careless:
        print(f"⚠️  剔除 {len(careless)} 份敷衍作答（按顺序点 + 总时长<120s + 非默认操作≤2）:")
        for sub in careless:
            dur_s = round(get_total_duration(sub) / 1000)
            uid = sub.get('userId', '匿名')
            print(f"   - {uid}: {dur_s}秒")
    print(f"📊 有效样本：{len(submissions)} 份\n")

    if not submissions:
        print("❌ 过滤后无有效数据")
        sys.exit(1)

    report = generate_report(submissions, invalid_count=len(invalid))
    print(report)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📄 报告已保存到: {args.output}")

if __name__ == '__main__':
    main()
