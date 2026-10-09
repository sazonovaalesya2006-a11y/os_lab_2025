#!/bin/bash
set -e

# Создание файла с кредами для s3fs
echo "${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}" > /etc/passwd-s3fs
chmod 600 /etc/passwd-s3fs

# Ожидание готовности MinIO
echo "Waiting for MinIO at ${S3_ENDPOINT}..."
until curl -sf "${S3_ENDPOINT}/minio/health/live"; do
    sleep 2
done
echo "MinIO is ready."

# Монтирование s3fs
s3fs ${S3_BUCKET} /mnt/s3 \
    -o passwd_file=/etc/passwd-s3fs \
    -o url=${S3_ENDPOINT} \
    -o use_path_request_style \
    -o allow_other \
    -o parallel_count=15 \
    -o multipart_size=52

echo "Mounted ${S3_BUCKET} at /mnt/s3"

# Держим контейнер запущенным
tail -f /dev/null
