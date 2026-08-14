# MinIO para Railway. Va como imagen propia y no como `--image minio/minio`
# porque la CLI de Railway no permite fijar el start command de un servicio de
# imagen, y minio/minio no arranca el server por defecto.
FROM minio/mc:latest AS mc

FROM minio/minio:latest

# `mc` no viene en la imagen del server; se copia para poder crear el bucket en
# el arranque (equivalente al servicio storage-init de docker-compose).
COPY --from=mc /usr/bin/mc /usr/bin/mc

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
