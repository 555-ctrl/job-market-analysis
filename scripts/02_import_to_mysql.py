"""
MySQL 数据导入工具
功能：将清洗后的招聘数据批量导入三表结构（岗位主表 + 技能字典 + 关联表）
配置通过环境变量注入

"""

import os
import pandas as pd
import pymysql
import argparse
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(description='导入数据至 MySQL')
    parser.add_argument('--input', type=str, default='data/cleaned_jobs.pkl', help='清洗后数据路径')
    return parser.parse_args()


def get_db_config():
    """
    从环境变量读取数据库配置
    环境变量: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    """
    return {
        'host': os.environ.get('MYSQL_HOST', 'localhost'),
        'user': os.environ.get('MYSQL_USER', 'root'),
        'password': os.environ.get('MYSQL_PASSWORD', ''),
        'database': os.environ.get('MYSQL_DATABASE', 'job_market'),
        'charset': 'utf8mb4'
    }


def main():
    args = parse_args()
    config = get_db_config()

    if not config['password']:
        print("[WARN] 未检测到 MYSQL_PASSWORD 环境变量，请确认数据库配置")

    print(f"[INFO] 加载数据: {args.input}")
    if args.input.endswith('.pkl'):
        df = pd.read_pickle(args.input)
    else:
        df = pd.read_csv(args.input)

    df = df.replace({float('nan'): None, pd.NA: None})
    print(f"[INFO] 待导入数据: {len(df)} 条")

    try:
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
    except pymysql.Error as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        exit(1)

    # 1. 技能字典表批量插入
    all_skills = set()
    for skills in df['skills_list']:
        all_skills.update(skills)

    print(f"[INFO] 插入技能字典: {len(all_skills)} 项")
    skill_id_map = {}
    for skill in tqdm(all_skills):
        cursor.execute("INSERT IGNORE INTO skills (skill_name) VALUES (%s)", (skill,))
        cursor.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill,))
        skill_id_map[skill] = cursor.fetchone()[0]
    conn.commit()

    # 2. 岗位主表批量插入
    print("[INFO] 插入岗位主表...")
    job_data = []
    for _, row in tqdm(df.iterrows(), total=len(df)):
        job_data.append((
            row.get('job_id', ''),
            row.get('title', ''),
            row.get('company_name', ''),
            row.get('location', ''),
            row.get('city', ''),
            row.get('state', ''),
            row.get('salary_yearly'),
            row.get('salary_min_clean'),
            row.get('salary_max_clean'),
            int(row.get('is_remote', 0)),
            row.get('schedule_type', ''),
            row.get('posted_at', ''),
            row.get('description', ''),
            int(row.get('skills_count', 0))
        ))

    cursor.executemany("""
        INSERT IGNORE INTO jobs 
        (job_id, title, company_name, location, city, state, salary_yearly, 
         salary_min, salary_max, is_remote, schedule_type, posted_at, description, skills_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, job_data)
    conn.commit()

    # 3. 岗位-技能关联表批量插入
    print("[INFO] 插入岗位-技能关联数据...")
    relation_data = []
    for _, row in tqdm(df.iterrows(), total=len(df)):
        job_id = row.get('job_id')
        skill_list = row.get('skills_list')
        if not skill_list:
            continue
        for skill in skill_list:
            skill_id = skill_id_map.get(skill)
            if skill_id:
                relation_data.append((job_id, skill_id))

    cursor.executemany(
        "INSERT IGNORE INTO job_skills (job_id, skill_id) VALUES (%s, %s)",
        relation_data
    )
    conn.commit()

    # 导入结果统计
    cursor.execute("SELECT COUNT(*) FROM jobs")
    job_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM skills")
    skill_count = cursor.fetchone()[0]

    print(f"\n[SUCCESS] 数据导入完成")
    print(f"  岗位记录: {job_count} 条")
    print(f"  技能条目: {skill_count} 条")
    print(f"  关联记录: {len(relation_data)} 条")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
