# 数据分析师招聘市场分析

通过Kaggle上的Data Analyst Job Postings数据集，从清洗招聘信息开始，按三表结构存进MySQL，跑统计和图表，最后用FastAPI把结果包成接口。项目初衷是用量化方式梳理数据分析岗位的真实需求、薪资水平与就业趋势，同时串联Python、SQL相关知识点。

脚本按`01`到`04`编号，顺序执行即可。MySQL是可选的。

## 技术栈

- 数据处理：Python、pandas、numpy
- 数据存储：MySQL、SQLAlchemy
- 分析可视化：matplotlib、seaborn
- 接口服务：FastAPI、uvicorn
- 部署：Docker、Render

## 目录结构

```text
.
├── README.md
├── api/          # FastAPI接口代码
├── data/         # 原始数据和清洗后的文件
├── scripts/      # 清洗、入库、分析、可视化脚本
├── sql/          # 建表语句和分析查询
├── output/       # 图表和CSV结果
├── Dockerfile
└── requirements.txt
```

## 环境

Python3.10及以上，MySQL可选。下面的命令依据Linux/macOS的bash，Windows上建议用WSL。

## 运行

拉仓库、建虚拟环境、装依赖：

```bash
git clone https://github.com/YOUR_USERNAME/job-market-analysis.git
cd job-market-analysis
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 1.数据清洗

把Kaggle下载的数据集放进`data/`，先确认`scripts/01_data_cleaning.py`里的输入路径和文件名对得上，然后执行：

```bash
python3 scripts/01_data_cleaning.py
```

脚本会解析薪资区间、提取技能关键词、标准化城市字段，清洗后的文件仍放在`data/`。

### 2.入库（可选）

先执行`sql/`里的建表语句，再按`scripts/02_import_to_mysql.py`里的连接配置填好本地MySQL的地址、库名和账号密码：

```bash
python3 scripts/02_import_to_mysql.py
```

### 3.分析与可视化

```bash
python3 scripts/03_analysis.py
python3 scripts/04_visualization.py
```

统计CSV和图表都落在`output/`。

### 4.启动接口

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000
```

打开`http://localhost:8000/api/stats`看全局统计，`/docs`是自动生成的接口文档。

## 数据发现

- SQL、Excel、Python出现频率最高，基本是数据分析岗的默认要求。
- 远程岗位的薪资中位数低于线下岗，样本里入门级远程岗位偏多，把整体拉低了；高薪远程岗对技能组合的要求明显更高。
- 岗位集中在少数几个科技产业发达的城市，不同城市的技能偏好和薪资区间差别不小。
- 同时要求SQL、Python和可视化工具的岗位，薪资比只要求单一技能的高出30%以上。

原始统计结果留在`output/`里。

## 部署

本地用Docker：

```bash
docker build -t job-analysis-api .
docker run -d -p 8000:8000 job-analysis-api
```

Render、Hugging Face这类平台绑定GitHub仓库后，Build Command填`pip install -r requirements.txt`，Start Command填：

```bash
cd api && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

端口从`PORT`环境变量取，勿写死8000，平台分配的端口不一定是这个。

## 说明

数据集来自Kaggle公开数据，只用于学习交流。
