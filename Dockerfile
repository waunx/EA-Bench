FROM python:3.11-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    bubblewrap libreoffice poppler-utils fonts-dejavu-core fonts-liberation \
    libseccomp2 python3-uno git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e '.[artifacts]'
ENV EA_BENCH_ANALYSIS_DEPS=/usr/local/lib/python3.11/site-packages
ENTRYPOINT ["python", "-m", "ea_bench"]
