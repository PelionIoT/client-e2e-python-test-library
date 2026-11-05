# syntax=docker/dockerfile:1.7
# This repo is public. ArmMbedCloud/device-simulator is private and
# IzumaNetworks/pelion-system-tests is internal, so the build fetches them at
# fixed commits over the forwarded ssh agent, and no file of theirs enters git.
FROM debian:bookworm-20241016-slim AS sources
ARG DEVICE_SIMULATOR_REF=a4a387ff8af4f92992c8e75461339454af677265
ARG SYSTEM_TESTS_REF=c9056ed471c2b59d3ab903fc9c57a985dd9ce5f9
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git openssh-client && rm -rf /var/lib/apt/lists/*
RUN --mount=type=ssh mkdir -p -m 0700 /root/.ssh \
    && ssh-keyscan -t ed25519 github.com >> /root/.ssh/known_hosts \
    && git init -q /opt/device-simulator \
    && git -C /opt/device-simulator fetch -q --depth 1 git@github.com:ArmMbedCloud/device-simulator.git "$DEVICE_SIMULATOR_REF" \
    && git -C /opt/device-simulator checkout -q FETCH_HEAD \
    && rm -rf /opt/device-simulator/.git \
    && git init -q /opt/system-tests \
    && git -C /opt/system-tests fetch -q --depth 1 git@github.com:IzumaNetworks/pelion-system-tests.git "$SYSTEM_TESTS_REF" \
    && git -C /opt/system-tests checkout -q FETCH_HEAD \
    && mkdir -p /opt/simulated_client \
    && cp /opt/system-tests/simulated_client/testapp.py /opt/system-tests/simulated_client/provision.py /opt/simulated_client/ \
    && rm -rf /opt/system-tests

# The device simulator, on the Python and OpenSSL 1.1 its pins were written for.
# python3-dtls declares OPENSSL_init_ssl with one argument, so the second is
# whatever the register holds, and OpenSSL 1.1.1k dereferences it. Declare both.
FROM python:3.6.15-slim-bullseye AS simulator
COPY --from=sources /opt/device-simulator /opt/device-simulator
RUN pip install --no-cache-dir wheel 'setuptools<58' && pip install --no-cache-dir -r /opt/device-simulator/requirements.txt
RUN D=/usr/local/lib/python3.6/site-packages/dtls && \
    sed -i 's/((c_int, "ret"), (c_uint64, "opts"),)),/((c_int, "ret"), (c_uint64, "opts"), (c_void_p, "settings"))),/' $D/openssl.py && \
    sed -i 's/^OPENSSL_init_ssl(0)$/OPENSSL_init_ssl(0, None)/' $D/sslconnection.py && \
    python -c 'import dtls'
RUN cp /usr/lib/x86_64-linux-gnu/libssl.so.1.1 /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 \
    /usr/lib/x86_64-linux-gnu/libffi.so.7 /usr/local/lib/

# The library and its suite, on the oldest Python its README names.
FROM python:3.8.20-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libc6-dev libffi-dev libssl-dev git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir wheel && pip install --no-cache-dir -r /tmp/requirements.txt
COPY --from=simulator /usr/local /opt/simulator-python
COPY --from=simulator /opt/device-simulator /opt/device-simulator
COPY . /work/client-e2e-python-test-library
COPY --from=sources /opt/simulated_client /work/client-e2e-python-test-library/simulated_client
WORKDIR /work/client-e2e-python-test-library
ENV PYTHONPATH=/work/client-e2e-python-test-library:/work/client-e2e-python-test-library/scripts
ENV SIMULATED_CLIENT_LOG=/tmp/simulated-client.log
