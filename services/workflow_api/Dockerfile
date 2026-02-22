FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services /app/services
COPY rag_corpus /app/rag_corpus
ENV PYTHONUNBUFFERED=1
CMD ["python","-m","services.workflow_api.run"]
