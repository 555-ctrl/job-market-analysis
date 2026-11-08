"""
招聘市场数据分析模块
分析维度：
1. 技能需求词频统计
2. 技能与薪资关联分析
3. 远程办公薪资对比
4. 地域岗位分布与薪资排名

"""

import pandas as pd
import numpy as np
import argparse
from collections import Counter
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='招聘市场多维度统计分析')
    parser.add_argument('--input', type=str, default='data/cleaned_jobs.pkl', help='清洗后数据路径')
    parser.add_argument('--output', type=str, default='output/', help='分析结果输出目录')
    return parser.parse_args()


def analyze_skill_frequency(df):
    """技能需求词频 Top 20"""
    print("\n" + "="*50)
    print("1. 技能需求热度 Top 20")
    print("="*50)

    all_skills = []
    for skills in df['skills_list']:
        all_skills.extend(skills)

    skill_counter = Counter(all_skills)
    total_jobs = len(df)
    top20 = skill_counter.most_common(20)

    for skill, count in top20:
        print(f"  {skill:15s} {count:5d}  ({count/total_jobs:.1%})")

    return pd.DataFrame(top20, columns=['skill', 'count'])


def analyze_skill_salary(df):
    # 技能与薪资关联分析，仅统计样本量≥30的技能
    print("\n" + "="*50)
    print("2. 高薪技能排名（按薪资中位数）")
    print("="*50)

    df_salary = df[df['salary_yearly'].notna()].copy()
    if len(df_salary) == 0:
        print("  无有效薪资数据，跳过分析")
        return pd.DataFrame()

    skill_salary_map = {}
    for _, row in df_salary.iterrows():
        sal = row['salary_yearly']
        for skill in row['skills_list']:
            if skill not in skill_salary_map:
                skill_salary_map[skill] = []
            skill_salary_map[skill].append(sal)

    results = []
    for skill, salaries in skill_salary_map.items():
        if len(salaries) >= 30:
            results.append({
                'skill': skill,
                'count': len(salaries),
                'median_salary': np.median(salaries),
                'avg_salary': np.mean(salaries)
            })

    res_df = pd.DataFrame(results).sort_values('median_salary', ascending=False)
    print(res_df.head(15).to_string(index=False))
    return res_df


def analyze_remote_trend(df):
    # 远程与非远程岗位薪资对比
    print("\n" + "="*50)
    print("3. 远程 vs 非远程 薪资对比")
    print("="*50)

    df_salary = df[df['salary_yearly'].notna()]
    remote = df_salary[df_salary['is_remote'] == 1]
    onsite = df_salary[df_salary['is_remote'] == 0]

    print(f"  远程岗位数: {len(remote)} (占比 {len(remote)/len(df_salary):.1%})")
    print(f"  非远程岗位数: {len(onsite)}")
    print(f"  远程薪资中位数: ${remote['salary_yearly'].median():,.0f}")
    print(f"  非远程薪资中位数: ${onsite['salary_yearly'].median():,.0f}")

    if len(remote) > 0 and len(onsite) > 0:
        diff = (remote['salary_yearly'].median() - onsite['salary_yearly'].median()) / onsite['salary_yearly'].median()
        print(f"  薪资差异: {diff:+.1%}")

    return remote, onsite


def analyze_location(df):
    # 地域分析：城市岗位量与薪资排名
    print("\n" + "="*50)
    print("4. 城市岗位规模 Top 15")
    print("="*50)

    city_df = df[~df['city'].isin(['remote', 'unknown', 'national'])]
    city_counts = city_df['city'].value_counts().head(15)
    print(city_counts.to_string())

    print("\n城市薪资中位数排名 Top 10（样本量≥20）")
    df_salary = df[df['salary_yearly'].notna()]
    city_salary = df_salary.groupby('city')['salary_yearly'].agg(['count', 'median'])
    city_salary = city_salary[city_salary['count'] >= 20].sort_values('median', ascending=False)
    print(city_salary.head(10).to_string())

    return city_counts, city_salary


def main():
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 加载数据: {args.input}")
    if args.input.endswith('.pkl'):
        df = pd.read_pickle(args.input)
    else:
        df = pd.read_csv(args.input)

    print(f"[INFO] 数据规模: {len(df)} 条，含薪资 {df['salary_yearly'].notna().sum()} 条")

    # 执行全维度分析
    skill_freq = analyze_skill_frequency(df)
    skill_sal = analyze_skill_salary(df)
    analyze_remote_trend(df)
    analyze_location(df)

    # 保存结果
    skill_freq.to_csv(output_dir / 'skill_frequency.csv', index=False)
    if not skill_sal.empty:
        skill_sal.to_csv(output_dir / 'skill_salary.csv', index=False)

    print(f"\n[SUCCESS] 分析完成，结果已保存至 {output_dir}")


if __name__ == '__main__':
    main()
