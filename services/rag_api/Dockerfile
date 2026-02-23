FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir sentence-transformers qdrant-client
COPY services /app/services
COPY rag_corpus /app/rag_corpus
COPY docs/knowledge_base /app/docs/knowledge_base
ENV PYTHONUNBUFFERED=1
CMD ["python","-m","services.rag_api.run"]
