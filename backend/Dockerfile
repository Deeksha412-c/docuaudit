FROM python:3.11-slim

WORKDIR /app

# CPU-only PyTorch. The default Linux build pulls several GB of GPU libraries you don't need.
RUN pip install --no-cache-dir --retries 10 --timeout 300 torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 300 -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]