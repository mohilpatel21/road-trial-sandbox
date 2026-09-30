#!/usr/bin/env bash
# Async post-edit formatter (registered in settings.json §2.1; completes the
# script set the settings reference — noted in the B0-04 report).
IN=$(cat); PY=$(command -v python3 || command -v python)
FP=$(echo "$IN" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")
case "$FP" in
  *.dart) dart format "$FP" >/dev/null 2>&1 || true ;;
esac
exit 0
