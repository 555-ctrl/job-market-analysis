"""
Data Analyst Job Postings - 数据清洗模块
功能：
- 自动兼容 CSV/Excel 格式输入
- 薪资字段标准化与异常值过滤
- 技能标签解析与兜底提取
- 地理位置标准化与远程标识整合
- 岗位去重与数据质量校验

"""

import pandas as pd
import numpy as np
import argparse
import ast
import re
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='招聘数据集清洗')
    parser.add_argument('--input', type=str, default='data/gsearch_jobs.csv', help='输入文件路径')
    parser.add_argument('--output', type=str, default='data/cleaned_jobs.csv', help='输出文件路径')
    return parser.parse_args()


def load_data(filepath):
    """
    读取数据文件，通过文件魔数自动识别格式，不依赖后缀名
    """
    filepath = Path(filepath)
    with open(filepath, 'rb') as f:
        magic = f.read(4)

    # xlsx 为 ZIP 格式，xls 为 OLE2 格式
    if magic[:2] == b'PK' or magic[:4] == b'\xd0\xcf\x11\xe0':
        df = pd.read_excel(filepath)
    else:
        try:
            df = pd.read_csv(filepath, low_memory=False, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, low_memory=False, encoding='latin-1')

    print(f"[INFO] 加载原始数据: {df.shape[0]} 行 × {df.shape[1]} 列")
    return df


def parse_skills(tokens_str):
    """
    将字符串形式的技能列表转换为 Python List
    输入示例: "['tableau', 'r', 'python']"
    """
    if pd.isna(tokens_str):
        return []
    if isinstance(tokens_str, list):
        return tokens_str
    try:
        result = ast.literal_eval(str(tokens_str))
        return [str(t).strip().lower() for t in result] if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []


# 技能词典：用于空标签场景下的正则兜底提取
_SKILL_DICT = [
    'python', 'sql', 'r', 'tableau', 'power bi', 'power_bi', 'excel',
    'sas', 'spss', 'spark', 'hadoop', 'hive', 'aws', 'azure', 'gcp',
    'machine learning', 'mysql', 'postgresql', 'mongodb', 'snowflake',
    'bigquery', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'scikit-learn',
    'git', 'docker', 'jira', 'agile', 'powerpoint', 'word', 'outlook',
    'etl', 'data warehouse', 'dax', 'alteryx', 'redshift', 'scala'
]


def extract_skills_from_desc(description):
    # 从职位描述中正则匹配提取技能，作为 description_tokens 为空时的兜底

    if pd.isna(description):
        return []
    desc = str(description).lower()
    return [s.replace(' ', '_') for s in _SKILL_DICT
            if re.search(r'\b' + re.escape(s) + r'\b', desc)]


def standardize_location(location):
    """
    标准化地理位置，返回 (city, state, location_clean)
    分类规则：远程岗位 / 全国范围 / 城市+州格式 / 其他
    """
    if pd.isna(location):
        return 'unknown', 'unknown', 'unknown'

    loc = str(location).strip()
    lower = loc.lower()

    if lower in ['anywhere', 'remote', 'work from home', 'home based']:
        return 'remote', 'remote', 'remote'
    if lower in ['united states', 'usa', 'us', 'national']:
        return 'national', 'national', 'national'

    m = re.match(r'^([^,]+),\s*([A-Z]{2})$', loc)
    if m:
        return m.group(1).strip(), m.group(2).strip(), loc

    return loc, 'unknown', loc


def clean_data(df):
    # 主清洗流程，共 8 步

    print("[INFO] 开始数据清洗...")

    # 1. 移除无业务价值的列
    for col in ['Unnamed: 0', 'thumbnail', 'commute_time']:
        if col in df.columns:
            df = df.drop(columns=col)

    # 2. 薪资字段：直接使用数据集已标准化的年薪数值
    df['salary_yearly'] = df.get('salary_standardized', np.nan)
    df['salary_min_clean'] = df.get('salary_min', np.nan)
    df['salary_max_clean'] = df.get('salary_max', np.nan)

    # 3. 技能标签解析与兜底
    print("[INFO] 解析技能标签...")
    df['skills_list'] = df['description_tokens'].apply(parse_skills)
    df['skills_count'] = df['skills_list'].apply(len)
    df['skills_str'] = df['skills_list'].apply(lambda x: ','.join(x))

    empty_mask = df['skills_count'] == 0
    if empty_mask.any():
        print(f"[INFO] 空标签岗位兜底提取技能: {empty_mask.sum()} 条")
        df.loc[empty_mask, 'skills_list'] = df.loc[empty_mask, 'description'].apply(extract_skills_from_desc)
        df.loc[empty_mask, 'skills_count'] = df.loc[empty_mask, 'skills_list'].apply(len)
        df.loc[empty_mask, 'skills_str'] = df.loc[empty_mask, 'skills_list'].apply(lambda x: ','.join(x))

    # 4. 地理位置标准化
    print("[INFO] 标准化地理位置...")
    loc_parsed = df['location'].apply(standardize_location)
    df['city'] = loc_parsed.apply(lambda x: x[0])
    df['state'] = loc_parsed.apply(lambda x: x[1])
    df['location_clean'] = loc_parsed.apply(lambda x: x[2])

    # 5. 远程岗位标识：字段标记 + 地点标记 双维度合并
    df['is_remote'] = ((df.get('work_from_home') == 1) | (df['city'] == 'remote')).astype(int)

    # 6. 日期字段格式化
    if 'date_time' in df.columns:
        df['date_time'] = pd.to_datetime(df['date_time'], errors='coerce')
        df['post_year'] = df['date_time'].dt.year
        df['post_month'] = df['date_time'].dt.month

    # 7. 薪资异常值过滤
    sal = df['salary_yearly']
    abnormal = sal.notna() & ((sal < 10000) | (sal > 500000))
    if abnormal.any():
        print(f"[INFO] 过滤薪资异常值: {abnormal.sum()} 条")
        df.loc[abnormal, 'salary_yearly'] = np.nan

    # 8. 按 job_id 去重
    if 'job_id' in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=['job_id'], keep='first')
        if len(df) != before:
            print(f"[INFO] 岗位去重: {before} → {len(df)}")

    print(f"[INFO] 清洗完成，输出数据规模: {df.shape}")
    return df


def save_data(df, output_path):
    """
    同时保存 CSV（通用）与 Pickle（保留列表类型，供后续分析使用）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_csv = df.copy()
    df_csv['skills_list'] = df_csv['skills_list'].apply(str)
    df_csv.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"[INFO] 已保存 CSV: {output_path}")

    df.to_pickle(output_path.with_suffix('.pkl'))
    print(f"[INFO] 已保存 Pickle: {output_path.with_suffix('.pkl')}")


def main():
    args = parse_args()
    df = load_data(args.input)
    df_clean = clean_data(df)
    save_data(df_clean, args.output)

    # 输出质量统计
    print("\n" + "=" * 50)
    print("数据清洗质量报告")
    print("=" * 50)
    print(f"总岗位数: {len(df_clean)}")
    print(f"含薪资数据: {df_clean['salary_yearly'].notna().sum()} ({df_clean['salary_yearly'].notna().mean():.1%})")
    print(f"远程岗位: {df_clean['is_remote'].sum()} ({df_clean['is_remote'].mean():.1%})")
    print(f"单岗平均技能数: {df_clean['skills_count'].mean():.2f}")

    sal = df_clean['salary_yearly'].dropna()
    if len(sal) > 0:
        print(f"\n薪资分布（年薪 USD）:")
        print(f"  中位数: ${sal.median():,.0f}")
        print(f"  均值: ${sal.mean():,.0f}")
        print(f"  25% 分位: ${sal.quantile(0.25):,.0f}")
        print(f"  75% 分位: ${sal.quantile(0.75):,.0f}")


if __name__ == '__main__':
    main()
