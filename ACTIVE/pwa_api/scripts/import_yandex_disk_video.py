#!/usr/bin/env python3
"""Import one public Yandex Disk video into a private S3-compatible bucket.

The source and transcoded files live only in a temporary directory. Credentials
are read from environment variables and are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

YANDEX_API = "https://cloud-api.yandex.net/v1/disk/public/resources"


def yandex_json(path: str, public_url: str) -> dict:
    query = urllib.parse.urlencode({"public_key": public_url})
    request = urllib.request.Request(
        f"{YANDEX_API}{path}?{query}",
        headers={"User-Agent": "IQ-Barakah-video-import/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download_source(public_url: str, destination: Path) -> dict:
    metadata = yandex_json("", public_url)
    if metadata.get("type") != "file" or metadata.get("media_type") != "video":
        raise RuntimeError("public link does not point to one video file")
    expected_size = int(metadata.get("size") or 0)
    if expected_size <= 0:
        raise RuntimeError("Yandex Disk returned an invalid file size")

    download = yandex_json("/download", public_url)
    href = download.get("href")
    if not href:
        raise RuntimeError("Yandex Disk did not return a download URL")

    request = urllib.request.Request(href, headers={"User-Agent": "IQ-Barakah-video-import/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            target.write(chunk)

    actual_size = destination.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(f"incomplete download: expected {expected_size} bytes, received {actual_size}")
    return metadata


def transcode_to_mp4(source: Path, destination: Path) -> None:
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-map_metadata", "-1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True)
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("ffmpeg did not create an MP4 file")


def private_s3_client():
    required = {
        "VIDEO_S3_ENDPOINT_URL": os.environ.get("VIDEO_S3_ENDPOINT_URL", "").strip(),
        "VIDEO_S3_REGION": os.environ.get("VIDEO_S3_REGION", "ru-central1").strip(),
        "VIDEO_S3_ACCESS_KEY_ID": os.environ.get("VIDEO_S3_ACCESS_KEY_ID", "").strip(),
        "VIDEO_S3_SECRET_ACCESS_KEY": os.environ.get("VIDEO_S3_SECRET_ACCESS_KEY", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=required["VIDEO_S3_ENDPOINT_URL"],
        region_name=required["VIDEO_S3_REGION"],
        aws_access_key_id=required["VIDEO_S3_ACCESS_KEY_ID"],
        aws_secret_access_key=required["VIDEO_S3_SECRET_ACCESS_KEY"],
    )


def upload_private(client, source: Path, bucket: str, key: str) -> None:
    from boto3.s3.transfer import TransferConfig

    client.upload_file(
        str(source),
        bucket,
        key,
        ExtraArgs={
            "ContentType": "video/mp4",
            "ContentDisposition": "inline",
            "CacheControl": "private, max-age=3600",
        },
        Config=TransferConfig(multipart_threshold=16 * 1024 * 1024, multipart_chunksize=16 * 1024 * 1024),
    )
    uploaded = client.head_object(Bucket=bucket, Key=key)
    if int(uploaded.get("ContentLength") or 0) != source.stat().st_size:
        raise RuntimeError("uploaded object size does not match the local MP4")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-url", required=True, help="Public Yandex Disk file URL")
    parser.add_argument("--video-id", required=True, help="Opaque lesson video id, for example a-01-intro")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from video_security import s3_video_key, validate_video_id

    validate_video_id(args.video_id)
    bucket = os.environ.get("VIDEO_S3_BUCKET", "").strip()
    prefix = os.environ.get("VIDEO_S3_KEY_PREFIX", "lesson-videos").strip()
    if not bucket:
        raise RuntimeError("VIDEO_S3_BUCKET is not configured")
    key = s3_video_key(prefix, args.video_id)

    with tempfile.TemporaryDirectory(prefix="iqb-video-import-") as directory:
        source = Path(directory) / "source.mov"
        output = Path(directory) / f"{args.video_id}.mp4"
        metadata = download_source(args.public_url, source)
        print(f"Downloaded private source: {metadata.get('name', 'video')} ({source.stat().st_size} bytes)")
        transcode_to_mp4(source, output)
        print(f"Prepared protected MP4: {output.stat().st_size} bytes")
        upload_private(private_s3_client(), output, bucket, key)
        print(f"Uploaded private object: s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
