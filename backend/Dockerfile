FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip setuptools msgpack \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall --yes pip setuptools msgpack

COPY . ./

RUN COMMERCE_ENV=development \
        DJANGO_SECRET_KEY=collectstatic-build-only-not-a-runtime-secret \
        python manage.py collectstatic --noinput \
    && useradd --create-home --uid 10001 commerce \
    && chown -R commerce:commerce /app

USER commerce

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
