import argparse
import os

from . import filesystem, native_s3, metrics, visualize


def main():
    parser = argparse.ArgumentParser(description="S3 benchmark: s3fs vs boto3")
    parser.add_argument("--mountpoint", default="/mnt/s3fs")
    parser.add_argument("--bucket", default="benchmark")
    parser.add_argument("--endpoint", default="http://localhost:9000")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--output", default="benchmark_results")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    benchmarks = [
        filesystem.FilesystemSequentialWrite(args.mountpoint),
        filesystem.FilesystemSequentialRead(args.mountpoint),
        filesystem.FilesystemRandomIO(args.mountpoint),
        filesystem.FilesystemSmallFiles(args.mountpoint),
        filesystem.FilesystemMetadataOps(args.mountpoint),
        native_s3.S3SequentialWrite(args.bucket, args.endpoint),
        native_s3.S3SequentialRead(args.bucket, args.endpoint),
        native_s3.S3RandomIO(args.bucket, args.endpoint),
        native_s3.S3SmallFiles(args.bucket, args.endpoint),
        native_s3.S3MetadataOps(args.bucket, args.endpoint),
    ]

    results = []
    for bench in benchmarks:
        try:
            result = bench.run(args.iterations)
            results.append(result)
        except Exception as e:
            print(f"[{bench.name}] FAILED: {e}")

    json_path = os.path.join(args.output, "results.json")
    metrics.save_results(results, json_path)
    print(f"\nSaved raw results: {json_path}")

    metrics.print_summary(results)
    visualize.make_all_plots(results, args.output)


if __name__ == "__main__":
    main()
