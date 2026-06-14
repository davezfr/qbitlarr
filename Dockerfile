FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN addgroup --system qbitlarr \
    && adduser --system --ingroup qbitlarr qbitlarr \
    && mkdir -p /app/data \
    && chown -R qbitlarr:qbitlarr /app

EXPOSE 8000

USER qbitlarr

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
