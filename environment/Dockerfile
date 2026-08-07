# hash:sha256:c407cc7a583d2476af7c4c68e1bca8be657e7333235f91ab10e8f15f8b1feda6
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/mambaforge3:24.5.0-0-python3.12.4-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GIT_ASKPASS
COPY git-ask-pass /

RUN pip install -U --no-cache-dir \
    aind-nwb-utils==0.2.8 \
    hdmf-zarr==0.13.0 \
    log-schema==0.2.10.dev1 \
    numpy==2.3.5 \
    pandas==2.3.3 \
    pydantic-settings==2.12.0 \
    watchtower==3.4.0
