FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY api/ ./api/
COPY data/data_cleaned.pkl ./data/data_cleaned.pkl

ENV DATA_FILE=/app/data/data_cleaned.pkl

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

