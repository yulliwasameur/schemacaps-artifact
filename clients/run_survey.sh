#!/bin/sh
# Client survey test protocol (Table 7). Creates pinned environments, runs each client against drift_server.py,
# and writes ../results/client_survey_tests.json.  Requires: python3.11, uv, node >= 20, npm, network for installs.
set -e
cd "$(dirname "$0")"
[ -d .venv-mcp1 ] || { uv venv -q .venv-mcp1 --python 3.11 && uv pip install -q --python .venv-mcp1/bin/python "mcp==1.27.0"; }
[ -d .venv-mcp2 ] || { uv venv -q .venv-mcp2 --python 3.11 && uv pip install -q --python .venv-mcp2/bin/python "mcp==2.2.0"; }
[ -d .venv-scan ] || { uv venv -q .venv-scan --python 3.11 && uv pip install -q --python .venv-scan/bin/python "mcp-scan==0.4.2"; }
[ -d node_modules ] || npm install --no-audit --no-fund --loglevel=error
{
  echo "["
  .venv-mcp1/bin/python test_py_sdk.py; echo ","
  .venv-mcp2/bin/python test_py_sdk.py; echo ","
  node test_ts_sdk.mjs | sed -n 1p; echo ","
  node test_ts_sdk.mjs | sed -n 2p; echo ","
  node test_vercel.mjs; echo ","
  .venv-scan/bin/python test_mcp_scan.py 2>/dev/null | tail -1
  echo "]"
} > ../results/client_survey_tests.json.tmp
python3 -c "import json; d=json.load(open('../results/client_survey_tests.json.tmp')); json.dump({'protocol': 'drift_server.py widens read_file mid-session (path pattern dropped, webhookUrl added, same name and description) and sends tools/list_changed; each client re-lists and calls read_file with a value only the new schema admits', 'observed': __import__('time').strftime('%Y-%m-%d'), 'results': d}, open('../results/client_survey_tests.json','w'), indent=1)"
rm -f ../results/client_survey_tests.json.tmp
echo "written results/client_survey_tests.json"
