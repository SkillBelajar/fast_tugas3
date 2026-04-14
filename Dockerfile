FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kita tidak meng-copy source code disini, karena akan di-mount lewat volume
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001", "--reload"]