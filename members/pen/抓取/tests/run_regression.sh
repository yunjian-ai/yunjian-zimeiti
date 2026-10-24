#!/bin/bash
# usage: tests/run_regression.sh [--with-media]
cd "$(dirname "$0")/.."; PY=${PY:-.venv/bin/python}; mkdir -p output/regression
while read name url; do
  [ -z "$name" ] && continue
  $PY scrape.py "$url" --out "output/regression/$name" --with-comments "$@" < /dev/null > "output/regression/$name.log" 2>&1; echo "$name exit=$?"
done < tests/regression_urls.txt
