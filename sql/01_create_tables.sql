-- Data Analyst Job Market - Database Schema
-- 三表设计：岗位主表 + 技能字典表 + 多对多关联表
-- 适配 MySQL 8.0+，字符集 utf8mb4

CREATE DATABASE IF NOT EXISTS job_market DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE job_market;

-- 1. 岗位主表
DROP TABLE IF EXISTS jobs;
CREATE TABLE jobs (
    job_id VARCHAR(64) PRIMARY KEY COMMENT '岗位唯一标识',
    title VARCHAR(255) NOT NULL COMMENT '岗位名称',
    company_name VARCHAR(255) COMMENT '公司名称',
    location VARCHAR(255) COMMENT '原始地点文本',
    city VARCHAR(128) COMMENT '标准化城市',
    state VARCHAR(32) COMMENT '州/省',
    salary_yearly DECIMAL(12,2) COMMENT '标准化年薪（USD）',
    salary_min DECIMAL(12,2) COMMENT '薪资区间下限',
    salary_max DECIMAL(12,2) COMMENT '薪资区间上限',
    is_remote TINYINT DEFAULT 0 COMMENT '是否远程岗位：1=是，0=否',
    schedule_type VARCHAR(64) COMMENT '用工类型：全职/兼职等',
    posted_at VARCHAR(64) COMMENT '发布时间文本',
    description TEXT COMMENT '岗位描述全文',
    skills_count INT DEFAULT 0 COMMENT '要求技能数量',
    INDEX idx_city (city),
    INDEX idx_salary (salary_yearly),
    INDEX idx_remote (is_remote),
    INDEX idx_company (company_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位信息主表';

-- 2. 技能字典表
DROP TABLE IF EXISTS skills;
CREATE TABLE skills (
    skill_id INT AUTO_INCREMENT PRIMARY KEY,
    skill_name VARCHAR(64) UNIQUE NOT NULL COMMENT '技能名称（小写）',
    INDEX idx_name (skill_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='技能维度字典表';

-- 3. 岗位-技能关联表
DROP TABLE IF EXISTS job_skills;
CREATE TABLE job_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    skill_id INT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE,
    UNIQUE KEY uk_job_skill (job_id, skill_id),
    INDEX idx_skill (skill_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位与技能关联表';

-- 4. 业务视图：岗位薪资+技能聚合视图，简化常用查询
CREATE OR REPLACE VIEW v_job_salary AS
SELECT j.job_id, j.title, j.company_name, j.city, j.salary_yearly, j.is_remote,
       GROUP_CONCAT(s.skill_name SEPARATOR ', ') AS skills
FROM jobs j
LEFT JOIN job_skills js ON j.job_id = js.job_id
LEFT JOIN skills s ON js.skill_id = s.skill_id
GROUP BY j.job_id;
