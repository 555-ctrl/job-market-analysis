-- 业务分析 SQL 查询集
-- 运行环境：MySQL 8.0+
-- 依赖表：jobs, skills, job_skills

USE job_market;

-- 1. 基础统计类

-- 1.1 全局：岗位总量、薪资披露率、远程占比
SELECT
    COUNT(*) AS total_jobs,
    COUNT(salary_yearly) AS jobs_with_salary,
    SUM(is_remote) AS remote_jobs,
    ROUND(SUM(is_remote)/COUNT(*)*100, 2) AS remote_rate_pct
FROM jobs;

-- 1.2 薪资整体分布：均值、中位数、极值、标准差
-- 中位数通过排序取中间位置实现
SELECT
    ROUND(AVG(salary_yearly), 0) AS avg_salary,
    ROUND((SELECT salary_yearly
           FROM (SELECT salary_yearly,
                        ROW_NUMBER() OVER (ORDER BY salary_yearly) AS rn,
                        COUNT(*) OVER () AS total
                 FROM jobs
                 WHERE salary_yearly IS NOT NULL) t
           WHERE rn = FLOOR((total+1)/2)), 0) AS median_salary,
    ROUND(MIN(salary_yearly), 0) AS min_salary,
    ROUND(MAX(salary_yearly), 0) AS max_salary,
    ROUND(STDDEV(salary_yearly), 0) AS salary_std
FROM jobs
WHERE salary_yearly IS NOT NULL
LIMIT 1;

-- 2. 技能维度分析（多表关联）

-- 2.1 技能需求热度 Top 20
SELECT
    s.skill_name,
    COUNT(js.job_id) AS job_count,
    ROUND(COUNT(js.job_id) / (SELECT COUNT(*) FROM jobs) * 100, 2) AS demand_rate_pct
FROM skills s
JOIN job_skills js ON s.skill_id = js.skill_id
GROUP BY s.skill_id, s.skill_name
ORDER BY job_count DESC
LIMIT 20;

-- 2.2 高薪分位（前25%）岗位的高频技能
SELECT
    s.skill_name,
    COUNT(*) AS high_salary_job_count
FROM skills s
JOIN job_skills js ON s.skill_id = js.skill_id
JOIN jobs j ON js.job_id = j.job_id
WHERE j.salary_yearly > (
    SELECT salary_yearly
    FROM (
        SELECT salary_yearly,
               ROW_NUMBER() OVER (ORDER BY salary_yearly) AS rn,
               COUNT(*) OVER () AS total
        FROM jobs WHERE salary_yearly IS NOT NULL
    ) t
    WHERE rn = CEIL(total * 0.75)
    LIMIT 1
)
GROUP BY s.skill_id, s.skill_name
ORDER BY high_salary_job_count DESC
LIMIT 15;

-- 2.3 同时要求 Python + SQL 的岗位规模与平均薪资
SELECT
    COUNT(*) AS job_count,
    ROUND(AVG(j.salary_yearly), 0) AS avg_salary
FROM jobs j
WHERE EXISTS (SELECT 1 FROM job_skills js1 JOIN skills s1 ON js1.skill_id = s1.skill_id
              WHERE js1.job_id = j.job_id AND s1.skill_name = 'python')
  AND EXISTS (SELECT 1 FROM job_skills js2 JOIN skills s2 ON js2.skill_id = s2.skill_id
              WHERE js2.job_id = j.job_id AND s2.skill_name = 'sql');

-- 3. 薪资维度分析（窗口函数）

-- 3.1 城市平均薪资排名
SELECT
    city,
    job_count,
    avg_salary,
    RANK() OVER (ORDER BY avg_salary DESC) AS salary_rank
FROM (
    SELECT
        city,
        COUNT(*) AS job_count,
        ROUND(AVG(salary_yearly), 0) AS avg_salary
    FROM jobs
    WHERE salary_yearly IS NOT NULL
      AND city NOT IN ('remote', 'unknown', 'national')
    GROUP BY city
    HAVING COUNT(*) >= 20
) t
ORDER BY avg_salary DESC;

-- 3.2 公司薪资中位数排名
SELECT
    company_name,
    job_count,
    median_salary,
    DENSE_RANK() OVER (ORDER BY median_salary DESC) AS salary_dense_rank
FROM (
    SELECT
        company_name,
        COUNT(*) AS job_count,
        ROUND(MAX(CASE WHEN rn = FLOOR((cnt+1)/2) THEN salary_yearly END), 0) AS median_salary
    FROM (
        SELECT
            company_name,
            salary_yearly,
            ROW_NUMBER() OVER (PARTITION BY company_name ORDER BY salary_yearly) AS rn,
            COUNT(*) OVER (PARTITION BY company_name) AS cnt
        FROM jobs
        WHERE salary_yearly IS NOT NULL
    ) t
    GROUP BY company_name
    HAVING COUNT(*) >= 10
) t2
ORDER BY median_salary DESC
LIMIT 20;

-- 3.3 各城市薪资 Top 3 岗位
SELECT
    city,
    title,
    company_name,
    salary_yearly
FROM (
    SELECT
        city, title, company_name, salary_yearly,
        ROW_NUMBER() OVER (PARTITION BY city ORDER BY salary_yearly DESC) AS rn
    FROM jobs
    WHERE salary_yearly IS NOT NULL
      AND city NOT IN ('remote', 'unknown', 'national')
) t
WHERE rn <= 3
ORDER BY city, salary_yearly DESC;

-- 4. 地域维度分析

-- 4.1 岗位规模 Top 15 城市
SELECT
    city,
    COUNT(*) AS job_count,
    ROUND(COUNT(salary_yearly)/COUNT(*)*100, 2) AS salary_disclosure_pct
FROM jobs
WHERE city NOT IN ('remote', 'unknown', 'national')
GROUP BY city
ORDER BY job_count DESC
LIMIT 15;

-- 4.2 按州统计岗位量与平均薪资
SELECT
    state,
    COUNT(*) AS job_count,
    ROUND(AVG(salary_yearly), 0) AS avg_salary
FROM jobs
WHERE state != 'unknown'
GROUP BY state
ORDER BY job_count DESC;

-- 5. 远程办公维度分析

-- 5.1 远程 vs 非远程 薪资对比
SELECT
    work_type,
    job_count,
    avg_salary,
    median_salary
FROM (
    SELECT
        CASE is_remote WHEN 1 THEN 'Remote' ELSE 'On-site' END AS work_type,
        COUNT(*) AS job_count,
        ROUND(AVG(salary_yearly), 0) AS avg_salary,
        ROUND(MAX(CASE WHEN rn = FLOOR((cnt+1)/2) THEN salary_yearly END), 0) AS median_salary
    FROM (
        SELECT
            is_remote,
            salary_yearly,
            ROW_NUMBER() OVER (PARTITION BY is_remote ORDER BY salary_yearly) AS rn,
            COUNT(*) OVER (PARTITION BY is_remote) AS cnt
        FROM jobs
        WHERE salary_yearly IS NOT NULL
    ) t
    GROUP BY is_remote
) t2;

-- 5.2 远程岗位热门技能 Top 10
SELECT
    s.skill_name,
    COUNT(*) AS job_count
FROM skills s
JOIN job_skills js ON s.skill_id = js.skill_id
JOIN jobs j ON js.job_id = j.job_id
WHERE j.is_remote = 1
GROUP BY s.skill_id, s.skill_name
ORDER BY job_count DESC
LIMIT 10;