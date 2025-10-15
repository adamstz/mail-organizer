FROM pytorch/pytorch:latest

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

EXPOSE 8080

# Start the service
CMD ["python", "service.py"]