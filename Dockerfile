FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_ENV=production \
    DJANGO_DEBUG=false

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install -r requirements.txt gunicorn==26.2.0

COPY manage.py ./manage.py
COPY asset_management/ ./asset_management/
COPY assets/ ./assets/
COPY build.sh start.sh ./
RUN chmod 0555 ./build.sh ./start.sh \
    && ./build.sh \
    && rm ./build.sh

EXPOSE 10000
USER 65534:65534
CMD ["./start.sh"]
