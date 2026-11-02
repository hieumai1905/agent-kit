#!/bin/sh
# A single local regression run. DOES NOT certify native write enforcement.
set -eu
cd "$(dirname "$0")"
python3 tools/release_acceptance.py
printf '\nXem báo cáo: release/ONE_SHOT_ACCEPTANCE.json\n'
printf 'Bản này luôn G2 = NOT_CERTIFIED, bất kể số test PASS.\n'
