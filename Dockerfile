# Step 1: Secure & Minimal Base Image
FROM python:3.11-slim

# Step 2: Environment Optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Step 3: Working Directory
WORKDIR /app

# Step 4: Layer Caching ke liye Dependencies Copy & Install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Step 5: Application Source Code Copy Karein
COPY assistant/ assistant/
COPY demo/ demo/

# Step 6: DevSecOps Principle - Non-Root User Setup
RUN useradd -u 10001 -m appuser && \
    chown -R appuser:appuser /app
USER appuser

# Step 7: Container Entrypoint
CMD ["python", "-m", "demo.simulate_alert"]
