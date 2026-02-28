FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE 8000
CMD ["python", "run.py"]
