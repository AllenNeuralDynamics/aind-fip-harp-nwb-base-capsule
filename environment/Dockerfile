# hash:sha256:46ec72c4185f4c671482b554a6cff4f0cfde2ee3e0d7c2c3961b4c83e083b82b
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/mambaforge3:24.5.0-0-python3.12.4-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GIT_ASKPASS
COPY git-askpass /

RUN pip install -U --no-cache-dir \
    aind-nwb-utils==0.1.4 \
    hdmf-zarr==0.12.0 \
    numpy==2.3.5 \
    pandas==2.3.3 \
    pydantic-settings==2.12.0 \
    pynwb==3.1.2
