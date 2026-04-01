#!/bin/bash
set -e

CMD="uv run opendataloader-pdf-hybrid --host 0.0.0.0 --port ${HYBRID_PORT:-5002}"

if [ "${HYBRID_FORCE_OCR}" = "true" ]; then
    CMD="${CMD} --force-ocr --ocr-lang ${HYBRID_OCR_LANG:-ko,en}"
    echo "Starting hybrid server with force-ocr (lang: ${HYBRID_OCR_LANG:-ko,en})"
else
    echo "Starting hybrid server with auto-detect OCR"
fi

exec ${CMD}
