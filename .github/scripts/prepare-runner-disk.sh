#!/bin/sh
set -eu

cleanup_root=${RUNNER_CLEANUP_ROOT:-/}
case "$cleanup_root" in
    /*) ;;
    *)
        echo "RUNNER_CLEANUP_ROOT must be an absolute path" >&2
        exit 2
        ;;
esac

echo "Disk before cleanup:"
df -h /

root_prefix=${cleanup_root%/}
for relative in \
    usr/local/lib/android \
    usr/share/dotnet \
    opt/ghc \
    usr/local/.ghcup \
    opt/hostedtoolcache/CodeQL
do
    target="${root_prefix}/${relative}"
    if [ -e "$target" ]; then
        sudo rm -rf --one-file-system -- "$target"
    fi
done

# Runner của job release là máy tạm và chưa chạy container nào của dự án. Xóa
# image/cache Docker cài sẵn để BuildKit có toàn bộ ổ đĩa cho CUDA image.
docker system prune --all --force

echo "Disk after cleanup:"
df -h /

available_kib=$(df --output=avail -k / | tail -n 1 | tr -d ' ')
minimum_kib=$((18 * 1024 * 1024))
if [ "$available_kib" -lt "$minimum_kib" ]; then
    echo "release build needs at least 18 GiB free; runner has $((available_kib / 1024 / 1024)) GiB" >&2
    exit 1
fi
