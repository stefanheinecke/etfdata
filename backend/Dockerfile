FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chmod +x start.sh

EXPOSE 8000

ENV DATABASE_HOST=db
ENV PORT=8000

CMD ["./start.sh"]
