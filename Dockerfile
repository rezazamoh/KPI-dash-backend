FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /root/.ssh

COPY ssh-key/id_ed25519 /root/.ssh/id_ed25519
COPY ssh-key/id_ed25519.pub /root/.ssh/id_ed25519.pub

RUN chmod 700 /root/.ssh \
    && chmod 600 /root/.ssh/id_ed25519 \
    && chmod 644 /root/.ssh/id_ed25519.pub 
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]