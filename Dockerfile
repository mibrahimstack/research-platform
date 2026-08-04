FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PIP_REQUIRE_HASHES=0

ARG INSTALL_ML=false
RUN python -m pip install --upgrade pip setuptools wheel

# Install core requirements (fast) and optionally ML/large packages
COPY requirements-core.txt ./requirements-core.txt
RUN pip install --no-cache-dir -r requirements-core.txt

COPY requirements-ml.txt ./requirements-ml.txt
RUN if [ "${INSTALL_ML}" = "true" ] ; then \
            pip install --no-cache-dir -r requirements-ml.txt ; \
        else \
            echo "Skipping ML deps (INSTALL_ML=${INSTALL_ML})" ; \
        fi

COPY . .

EXPOSE 8000 8501

CMD ["python", "run_services.py"]
