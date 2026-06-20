FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (overridden by a bind mount in docker-compose for live reload)
COPY . .

EXPOSE 8000

# --reload watches for source changes; docker-compose mounts ./backend over this
# so edits on the host are picked up without rebuilding the image.
CMD ["uvicorn", "src.api:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]