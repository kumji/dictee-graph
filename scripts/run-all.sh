#!/usr/bin/env bash
# CSV -> graph.jsonld -> graph.json -> URI 페이지 파이프라인을 순서대로 실행한 뒤 dev 서버를 띄운다.
# 사용법: ./scripts/run-all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "========================================================"
echo "[1/4] CSV -> graph.jsonld + vocab.jsonld (scripts/build-jsonld.py)"
echo "========================================================"
python3 scripts/build-jsonld.py

echo
echo "========================================================"
echo "[2/4] graph.jsonld -> graph.json (scripts/build-graph-json.py)"
echo "========================================================"
python3 scripts/build-graph-json.py

echo
echo "========================================================"
echo "[3/4] JSON-LD -> 엔티티·predicate URI 페이지 (scripts/build-pages.py)"
echo "========================================================"
python3 scripts/build-pages.py

echo
echo "========================================================"
echo "[4/4] dev 서버 실행 (Ctrl+C로 종료)"
echo "========================================================"
npm run dev
