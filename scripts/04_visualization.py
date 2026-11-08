"""
数据可视化模块
生成6类标准分析图表，统一使用英文标签以兼容多环境部署

"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
from pathlib import Path
from collections import Counter


def parse_args():
    parser = argparse.ArgumentParser(description='生成分析可视化图表')
    parser.add_argument('--input', type=str, default='data/cleaned_jobs.pkl')
    parser.add_argument('--output', type=str, default='output/')
    return parser.parse_args()


def set_style():
    sns.set_theme(style="whitegrid", font_scale=1.1)
    plt.rcParams['axes.unicode_minus'] = False


def plot_skill_frequency(df, output_dir):
    # Top 15 技能需求柱状图
    all_skills = []
    for skills in df['skills_list']:
        all_skills.extend(skills)

    top15 = Counter(all_skills).most_common(15)
    skills, counts = zip(*top15)

    plt.figure(figsize=(12, 7))
    bars = plt.barh(range(len(skills)), counts, color='#4C72B0')
    plt.yticks(range(len(skills)), skills)
    plt.gca().invert_yaxis()
    plt.xlabel('Number of Job Postings')
    plt.title('Top 15 Most In-Demand Skills', fontsize=14, pad=15)

    for bar, count in zip(bars, counts):
        plt.text(bar.get_width() + 80, bar.get_y() + bar.get_height()/2,
                 f'{count}', va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / 'skill_frequency.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("skill_frequency.png")


def plot_salary_distribution(df, output_dir):
    # 薪资分布直方图
    df_sal = df[df['salary_yearly'].notna()]
    if len(df_sal) == 0:
        return

    plt.figure(figsize=(10, 6))
    sns.histplot(df_sal['salary_yearly'], bins=30, kde=True, color='#55A868')
    plt.axvline(df_sal['salary_yearly'].median(), color='red', linestyle='--',
                label=f'Median: ${df_sal["salary_yearly"].median():,.0f}')
    plt.xlabel('Annual Salary (USD)')
    plt.ylabel('Number of Jobs')
    plt.title('Data Analyst Salary Distribution', fontsize=14, pad=15)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / 'salary_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("salary_distribution.png")


def plot_remote_salary_boxplot(df, output_dir):
    # 远程与非远程薪资箱线图
    df_sal = df[df['salary_yearly'].notna()].copy()
    if len(df_sal) == 0:
        return

    df_sal['Work Type'] = df_sal['is_remote'].map({1: 'Remote', 0: 'On-site'})

    plt.figure(figsize=(8, 7))
    sns.boxplot(x='Work Type', y='salary_yearly', hue='Work Type',
                data=df_sal, palette=['#DD8452', '#4C72B0'], legend=False)
    plt.ylabel('Annual Salary (USD)')
    plt.title('Salary Comparison: Remote vs On-site', fontsize=14, pad=15)
    plt.tight_layout()
    plt.savefig(output_dir / 'remote_salary_boxplot.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("remote_salary_boxplot.png")


def plot_city_salary_heatmap(df, output_dir):
    # 城市-技能需求热力图
    city_df = df[~df['city'].isin(['remote', 'unknown', 'national'])]
    top_cities = city_df['city'].value_counts().head(8).index.tolist()

    all_skills = []
    for s in df['skills_list']:
        all_skills.extend(s)
    top_skills = [s for s, _ in Counter(all_skills).most_common(8)]

    matrix = pd.DataFrame(index=top_cities, columns=top_skills, data=0.0)
    for _, row in df.iterrows():
        if row['city'] in top_cities:
            for skill in row['skills_list']:
                if skill in top_skills:
                    matrix.loc[row['city'], skill] += 1

    city_counts = city_df['city'].value_counts()
    for city in top_cities:
        matrix.loc[city] = matrix.loc[city] / city_counts[city]

    plt.figure(figsize=(10, 7))
    sns.heatmap(matrix, annot=True, fmt='.1%', cmap='Blues')
    plt.title('Skill Demand Heatmap by City', fontsize=14, pad=15)
    plt.tight_layout()
    plt.savefig(output_dir / 'city_skill_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("city_skill_heatmap.png")


def plot_top_cities_bar(df, output_dir):
    # 城市岗位规模 Top 10 柱状图
    city_df = df[~df['city'].isin(['remote', 'unknown', 'national'])]
    top10 = city_df['city'].value_counts().head(10)

    plt.figure(figsize=(12, 6))
    top10.plot(kind='bar', color='#8172B2')
    plt.ylabel('Number of Job Postings')
    plt.title('Top 10 Cities by Job Volume', fontsize=14, pad=15)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / 'top_cities.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("top_cities.png")


def plot_skill_count_salary(df, output_dir):
    # 技能数量与薪资关系折线图
    df_sal = df[df['salary_yearly'].notna()]
    if len(df_sal) == 0:
        return

    grouped = df_sal.groupby('skills_count')['salary_yearly'].median().reset_index()
    grouped = grouped[grouped['skills_count'] <= 10]

    plt.figure(figsize=(10, 6))
    sns.lineplot(x='skills_count', y='salary_yearly', data=grouped,
                 marker='o', linewidth=2, color='#CCB974')
    plt.xlabel('Number of Required Skills')
    plt.ylabel('Median Annual Salary (USD)')
    plt.title('Relationship Between Skill Count and Salary', fontsize=14, pad=15)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'skill_count_salary.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("skill_count_salary.png")


def main():
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    set_style()

    print(f"[INFO] 加载数据: {args.input}")
    if args.input.endswith('.pkl'):
        df = pd.read_pickle(args.input)
    else:
        df = pd.read_csv(args.input)

    plot_skill_frequency(df, output_dir)
    plot_salary_distribution(df, output_dir)
    plot_remote_salary_boxplot(df, output_dir)
    plot_city_salary_heatmap(df, output_dir)
    plot_top_cities_bar(df, output_dir)
    plot_skill_count_salary(df, output_dir)

    print(f"\n[SUCCESS] 所有图表已生成，保存路径: {output_dir}")


if __name__ == '__main__':
    main()
