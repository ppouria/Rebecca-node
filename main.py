import os

import uvicorn

import rest_service
from certificate import generate_certificate
from config import (
    SERVICE_HOST,
    SERVICE_PORT,
    SSL_CERT_FILE,
    SSL_KEY_FILE,
    SSL_CLIENT_CERT_FILE,
)
from logger import logger


def generate_ssl_files():
    pems = generate_certificate()

    with open(SSL_KEY_FILE, "w") as f:
        f.write(pems["key"])

    with open(SSL_CERT_FILE, "w") as f:
        f.write(pems["cert"])


if __name__ == "__main__":
    if not all((os.path.isfile(SSL_CERT_FILE), os.path.isfile(SSL_KEY_FILE))):
        generate_ssl_files()

    if not SSL_CLIENT_CERT_FILE or not os.path.isfile(SSL_CLIENT_CERT_FILE):
        logger.error("SSL_CLIENT_CERT_FILE is required for the REST service.")
        raise SystemExit(1)

    logger.info(f"Node service running on :{SERVICE_PORT}")
    uvicorn.run(
        rest_service.app,
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        ssl_keyfile=SSL_KEY_FILE,
        ssl_certfile=SSL_CERT_FILE,
        ssl_ca_certs=SSL_CLIENT_CERT_FILE,
        ssl_cert_reqs=2,
    )
