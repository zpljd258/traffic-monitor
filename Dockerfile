FROM python:3.13.2-alpine3.21

WORKDIR /app

COPY traffic_monitor.py .

RUN pip install requests

CMD ["python", "/app/traffic_monitor.py"]
