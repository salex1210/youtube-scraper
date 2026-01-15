FROM python:3.10.2-slim as base

WORKDIR /app

COPY . .

RUN python -m pip install -r requirements.txt

RUN playwright install --with-deps chromium

CMD python ./main.py