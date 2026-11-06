ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/arp
COPY requirements.lock requirements-build.lock requirements.in pyproject.toml ./
RUN python -I -m pip install --no-cache-dir --require-hashes -r requirements.lock -r requirements-build.lock
COPY apps/control apps/control
COPY packages/contracts packages/contracts
RUN python -I -m pip install --no-cache-dir --no-deps --no-build-isolation . \
    && useradd --uid 10001 --create-home arp \
    && mkdir -p /var/lib/arp/objects \
    && chown arp:arp /var/lib/arp/objects
USER 10001:10001
EXPOSE 8000
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "--threads=4", "--max-request-body-size=1048576", "arp_control.wsgi:application"]
