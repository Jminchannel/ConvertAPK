FROM docker:27-cli AS dockercli

FROM python:3.12-slim

# backend 会通过宿主机 docker.sock 调用 apk-builder 镜像，因此需要 docker CLI
# 为了避免云服务器构建时 apt-get 过慢/超时，这里直接从官方 docker:cli 镜像拷贝二进制
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app/apps/web/backend

# pip 镜像（国内服务器构建更稳定；如需可在 build 时覆盖）
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
ARG PIP_TRUSTED_HOST=mirrors.cloud.tencent.com
ARG PIP_FALLBACK_INDEX_URLS="https://pypi.tuna.tsinghua.edu.cn/simple https://mirrors.aliyun.com/pypi/simple https://pypi.mirrors.ustc.edu.cn/simple"
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=100

COPY apps/web/backend/requirements.txt /app/apps/web/backend/requirements.txt
RUN set -e; \
    install_with_index() { \
      index_url="$1"; \
      trusted_host="$2"; \
      echo "[pip] index: $index_url"; \
      python -m pip install --no-cache-dir --retries 10 --timeout 100 \
        -i "$index_url" --trusted-host "$trusted_host" \
        -r requirements.txt; \
    }; \
    if install_with_index "$PIP_INDEX_URL" "$PIP_TRUSTED_HOST"; then \
      exit 0; \
    fi; \
    for index_url in $PIP_FALLBACK_INDEX_URLS; do \
      trusted_host="$(echo "$index_url" | awk -F/ '{print $3}')"; \
      if install_with_index "$index_url" "$trusted_host"; then \
        exit 0; \
      fi; \
    done; \
    echo "[pip] WARNING: all mirrors failed, fallback to official (may be slow)"; \
    python -m pip install --no-cache-dir --retries 10 --timeout 100 -r requirements.txt

COPY apps/web/backend/ /app/apps/web/backend/
COPY templates/android/ /app/templates/
COPY workers/apk-worker/ /app/workers/apk-worker/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
