"""
Data Analyst Job Market Analysis API
基于 FastAPI 实现的招聘市场数据查询接口
- 兼容 Hugging Face Spaces 部署（自动读取 PORT 环境变量）
- 支持 Docker 容器化运行
- 默认本地文件数据源，可选 MySQL 数据源
- 全量配置通过环境变量注入

"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from collections import Counter
import pandas as pd
import numpy as np
import ast
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / 'data'
DATA_FILE = os.environ.get('DATA_FILE', str(DATA_DIR / 'data_cleaned.pkl'))

# MySQL 可选配置
MYSQL_ENABLED = os.environ.get('MYSQL_ENABLED', 'false').lower() == 'true'
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'job_market')

# 数据加载
def load_data():
    # 优先加载 MySQL，失败自动回退至本地文件
    if MYSQL_ENABLED:
        try:
            from sqlalchemy import create_engine
            from urllib.parse import quote_plus
            db_url = f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
            engine = create_engine(db_url)
            df = pd.read_sql("SELECT * FROM jobs", engine)

            skills_df = pd.read_sql("""
                SELECT js.job_id, s.skill_name
                FROM job_skills js
                JOIN skills s ON js.skill_id = s.skill_id
            """, engine)
            skills_grouped = skills_df.groupby('job_id')['skill_name'].apply(list)
            df['skills_list'] = df['job_id'].map(skills_grouped).fillna('').apply(
                lambda x: x if isinstance(x, list) else [])
            df['skills_count'] = df['skills_list'].apply(len)
            return df
        except Exception as e:
            print(f"[WARN] MySQL 连接失败，回退至本地文件: {str(e)}")

    filepath = Path(DATA_FILE)
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    if filepath.suffix == '.pkl':
        df = pd.read_pickle(filepath)
    elif filepath.suffix == '.csv':
        df = pd.read_csv(filepath, low_memory=False)
        if 'skills_list' in df.columns:
            df['skills_list'] = df['skills_list'].apply(_parse_skills_str)
    else:
        raise ValueError(f"Unsupported file format: {filepath.suffix}")

    if 'salary_yearly' not in df.columns and 'salary_standardized' in df.columns:
        df['salary_yearly'] = df['salary_standardized']

    return df


def _parse_skills_str(s):
    if pd.isna(s):
        return []
    if isinstance(s, list):
        return s
    try:
        result = ast.literal_eval(str(s))
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []


# 全局数据缓存
_df_cache = None


def get_df():
    global _df_cache
    if _df_cache is None:
        _df_cache = load_data()
    return _df_cache

# 响应模型
class SkillStats(BaseModel):
    skill: str
    job_count: int
    job_percentage: float
    avg_salary: Optional[float] = None
    median_salary: Optional[float] = None
    top_cities: List[Dict[str, Any]] = []
    remote_count: int


class CityStats(BaseModel):
    city: str
    job_count: int
    avg_salary: Optional[float] = None
    median_salary: Optional[float] = None
    top_skills: List[Dict[str, Any]] = []
    remote_count: int


class StatsOverview(BaseModel):
    total_jobs: int
    jobs_with_salary: int
    remote_jobs: int
    remote_percentage: float
    avg_salary: Optional[float] = None
    median_salary: Optional[float] = None
    total_skills: int
    top_skills: List[Dict[str, Any]] = []
    top_cities: List[Dict[str, Any]] = []


class JobInfo(BaseModel):
    title: str
    company_name: str
    location: str
    salary_standardized: Optional[float] = None
    is_remote: int
    skills: List[str] = []

# FastAPI 应用
app = FastAPI(
    title="Data Analyst Job Market API",
    description="基于 Kaggle Data Analyst Job Postings 数据集的招聘市场分析接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    global _df_cache
    _df_cache = load_data()


@app.get("/api/skill/{skill_name}", response_model=SkillStats,
         summary="查询技能统计信息")
async def get_skill_stats(skill_name: str):
    data = get_df()
    skill_lower = skill_name.lower().strip()

    mask = data['skills_list'].apply(
        lambda x: skill_lower in [s.lower() for s in x] if isinstance(x, list) else False
    )
    skill_jobs = data[mask]

    if len(skill_jobs) == 0:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    salary_jobs = skill_jobs[skill_jobs['salary_yearly'].notna()]
    avg_salary = float(salary_jobs['salary_yearly'].mean()) if len(salary_jobs) > 0 else None
    median_salary = float(salary_jobs['salary_yearly'].median()) if len(salary_jobs) > 0 else None

    city_counts = skill_jobs['city'].value_counts().head(5)
    top_cities = [
        {"city": city, "count": int(count),
         "avg_salary": float(skill_jobs[skill_jobs['city'] == city]['salary_yearly'].mean())
         if skill_jobs[skill_jobs['city'] == city]['salary_yearly'].notna().any() else None}
        for city, count in city_counts.items()
    ]

    return SkillStats(
        skill=skill_lower,
        job_count=int(len(skill_jobs)),
        job_percentage=round(len(skill_jobs) / len(data) * 100, 2),
        avg_salary=round(avg_salary, 0) if avg_salary else None,
        median_salary=round(median_salary, 0) if median_salary else None,
        top_cities=top_cities,
        remote_count=int(skill_jobs['is_remote'].sum())
    )


@app.get("/api/city/{city_name}", response_model=CityStats,
         summary="查询城市统计信息")
async def get_city_stats(city_name: str):
    data = get_df()
    city_lower = city_name.lower().strip()

    mask = data['city'].str.lower().str.contains(city_lower, na=False)
    mask = mask | data['location_clean'].str.lower().str.contains(city_lower, na=False)
    city_jobs = data[mask]

    if len(city_jobs) == 0:
        raise HTTPException(status_code=404, detail=f"City '{city_name}' not found")

    salary_jobs = city_jobs[city_jobs['salary_yearly'].notna()]
    avg_salary = float(salary_jobs['salary_yearly'].mean()) if len(salary_jobs) > 0 else None
    median_salary = float(salary_jobs['salary_yearly'].median()) if len(salary_jobs) > 0 else None

    all_skills = []
    for skills in city_jobs['skills_list']:
        if isinstance(skills, list):
            all_skills.extend(skills)
    skill_counter = Counter(all_skills)
    top_skills = [
        {"skill": skill, "count": count,
         "percentage": round(count / len(city_jobs) * 100, 1)}
        for skill, count in skill_counter.most_common(5)
    ]

    actual_city = city_jobs['city'].mode().iloc[0] if len(city_jobs) > 0 else city_name
    return CityStats(
        city=actual_city,
        job_count=int(len(city_jobs)),
        avg_salary=round(avg_salary, 0) if avg_salary else None,
        median_salary=round(median_salary, 0) if median_salary else None,
        top_skills=top_skills,
        remote_count=int(city_jobs['is_remote'].sum())
    )


@app.get("/api/skills", summary="获取全量技能列表")
async def get_all_skills(
    limit: int = Query(50, ge=1, le=500),
    min_count: int = Query(1, ge=1)
):
    data = get_df()
    all_skills = []
    for skills in data['skills_list']:
        if isinstance(skills, list):
            all_skills.extend(skills)
    skill_counter = Counter(all_skills)

    result = [
        {"skill": skill, "count": count,
         "percentage": round(count / len(data) * 100, 2)}
        for skill, count in skill_counter.most_common()
        if count >= min_count
    ][:limit]
    return {"total": len(result), "skills": result}


@app.get("/api/cities", summary="获取城市岗位列表")
async def get_all_cities(
    limit: int = Query(50, ge=1, le=500),
    min_jobs: int = Query(1, ge=1)
):
    data = get_df()
    city_stats = data[~data['city'].isin(['remote', 'national', 'unknown'])].groupby('city').agg(
        job_count=('job_id', 'count'),
        avg_salary=('salary_yearly', 'mean')
    ).reset_index()

    city_stats = city_stats[city_stats['job_count'] >= min_jobs]
    city_stats = city_stats.sort_values('job_count', ascending=False).head(limit)

    result = [
        {"city": row['city'], "job_count": int(row['job_count']),
         "avg_salary": round(float(row['avg_salary']), 0) if pd.notna(row['avg_salary']) else None}
        for _, row in city_stats.iterrows()
    ]
    return {"total": len(result), "cities": result}


@app.get("/api/stats", response_model=StatsOverview, summary="全局统计概览")
async def get_stats():
    data = get_df()
    salary_data = data[data['salary_yearly'].notna()]
    avg_salary = float(salary_data['salary_yearly'].mean()) if len(salary_data) > 0 else None
    median_salary = float(salary_data['salary_yearly'].median()) if len(salary_data) > 0 else None

    all_skills = []
    for skills in data['skills_list']:
        if isinstance(skills, list):
            all_skills.extend(skills)
    skill_counter = Counter(all_skills)
    top_skills = [
        {"skill": s, "count": c, "percentage": round(c / len(data) * 100, 1)}
        for s, c in skill_counter.most_common(10)
    ]

    city_counts = data[~data['city'].isin(['remote', 'national', 'unknown'])]['city'].value_counts().head(10)
    top_cities = [{"city": city, "count": int(count)} for city, count in city_counts.items()]

    return StatsOverview(
        total_jobs=int(len(data)),
        jobs_with_salary=int(len(salary_data)),
        remote_jobs=int(data['is_remote'].sum()),
        remote_percentage=round(data['is_remote'].mean() * 100, 2),
        avg_salary=round(avg_salary, 0) if avg_salary else None,
        median_salary=round(median_salary, 0) if median_salary else None,
        total_skills=len(skill_counter),
        top_skills=top_skills,
        top_cities=top_cities
    )


@app.get("/api/high-salary", summary="高薪岗位列表")
async def get_high_salary_jobs(
    threshold: float = Query(100000, description="年薪阈值，单位 USD"),
    limit: int = Query(20, ge=1, le=100)
):
    data = get_df()
    high_salary = data[data['salary_yearly'] >= threshold].sort_values(
        'salary_yearly', ascending=False).head(limit)

    jobs = []
    for _, row in high_salary.iterrows():
        jobs.append(JobInfo(
            title=row['title'],
            company_name=row['company_name'],
            location=row['location_clean'],
            salary_standardized=float(row['salary_yearly']),
            is_remote=int(row['is_remote']),
            skills=row['skills_list'] if isinstance(row['skills_list'], list) else []
        ))
    return {"threshold": threshold, "count": len(jobs), "jobs": jobs}


@app.get("/api/remote", summary="远程岗位分析")
async def get_remote_analysis():
    data = get_df()
    remote = data[data['is_remote'] == 1]
    onsite = data[data['is_remote'] == 0]

    remote_salary = remote[remote['salary_yearly'].notna()]['salary_yearly']
    onsite_salary = onsite[onsite['salary_yearly'].notna()]['salary_yearly']

    remote_skills = []
    for skills in remote['skills_list']:
        if isinstance(skills, list):
            remote_skills.extend(skills)
    top_remote_skills = [{"skill": s, "count": c} for s, c in Counter(remote_skills).most_common(10)]

    return {
        "remote": {
            "count": int(len(remote)),
            "percentage": round(len(remote) / len(data) * 100, 2),
            "avg_salary": round(float(remote_salary.mean()), 0) if len(remote_salary) > 0 else None,
            "median_salary": round(float(remote_salary.median()), 0) if len(remote_salary) > 0 else None,
            "top_skills": top_remote_skills
        },
        "onsite": {
            "count": int(len(onsite)),
            "percentage": round(len(onsite) / len(data) * 100, 2),
            "avg_salary": round(float(onsite_salary.mean()), 0) if len(onsite_salary) > 0 else None,
            "median_salary": round(float(onsite_salary.median()), 0) if len(onsite_salary) > 0 else None
        }
    }


@app.get("/api/compare-skills", summary="多技能对比")
async def compare_skills(skills: str = Query(..., description="逗号分隔的技能名，如 python,sql,r")):
    data = get_df()
    skill_list = [s.strip().lower() for s in skills.split(',')]
    results = []

    for skill in skill_list:
        mask = data['skills_list'].apply(
            lambda x: skill in [s.lower() for s in x] if isinstance(x, list) else False
        )
        skill_jobs = data[mask]
        salary_data = skill_jobs[skill_jobs['salary_yearly'].notna()]

        results.append({
            "skill": skill,
            "job_count": int(len(skill_jobs)),
            "job_percentage": round(len(skill_jobs) / len(data) * 100, 2),
            "avg_salary": round(float(salary_data['salary_yearly'].mean()), 0) if len(salary_data) > 0 else None,
            "median_salary": round(float(salary_data['salary_yearly'].median()), 0) if len(salary_data) > 0 else None,
            "remote_count": int(skill_jobs['is_remote'].sum())
        })
    return {"comparison": results}


@app.get("/", summary="服务信息")
async def root():
    return {
        "name": "Data Analyst Job Market Analysis API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "GET /api/stats": "全局统计概览",
            "GET /api/skill/{skill_name}": "技能详情查询",
            "GET /api/city/{city_name}": "城市详情查询",
            "GET /api/skills": "全量技能列表",
            "GET /api/cities": "全量城市列表",
            "GET /api/high-salary": "高薪岗位列表",
            "GET /api/remote": "远程岗位分析",
            "GET /api/compare-skills": "多技能对比"
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
