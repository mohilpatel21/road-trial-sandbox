#!/usr/bin/env bash
# The dummy app test: every lib/ file must be listed in lib/INDEX.txt, and none may say RED.
set -u
fail=0
for f in lib/*.txt; do
  name=$(basename "$f")
  [ "$name" = INDEX.txt ] && continue
  if grep -q RED "$f"; then echo "FAIL: $f says RED"; fail=1; fi
  if ! grep -qx "$name" lib/INDEX.txt; then echo "FAIL: $f is not listed in lib/INDEX.txt"; fail=1; fi
done
[ "$fail" -eq 0 ] && echo "check: ok"
exit "$fail"
