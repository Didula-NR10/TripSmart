# Tripsmart backend — Hugging Face Spaces (Docker SDK).
#
# HF Spaces sends traffic to port 7860 and runs the container as a non-root
# user by convention (see https://huggingface.co/docs/hub/spaces-sdks-docker).
FROM python:3.12-slim

# TensorFlow needs libgomp at runtime; everything else in requirements.txt
# ships manylinux wheels, so no compiler toolchain is required.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
