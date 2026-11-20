#!/usr/bin/env bash
# Make generatedSchema.usda and plugInfo.json from schema.usda. Run after editing it.
#
# The schemas are codeless: USD reads these two files and nothing is compiled. The generator
# is OpenUSD's usdGenSchema.py (from a clone of OpenUSD: $OPENUSD), run with usd-core.
#
# Needs bash and GNU sed (Linux; on Windows, Git Bash or WSL). Only for changing the schemas:
# using the library needs neither.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENUSD="${OPENUSD:-$HERE/../OpenUSD}"
GENERATOR="$OPENUSD/pxr/usd/usd/usdGenSchema.py"

cd "$HERE/src/usdsensors/schema"
uv run -q --project "$HERE" --with jinja2 python "$GENERATOR" schema.usda . >/dev/null
# The generator leaves these for a build system to fill in; there is none.
sed -i -e 's|@PLUG_INFO_LIBRARY_PATH@||' -e 's|@PLUG_INFO_RESOURCE_PATH@|.|' -e 's|@PLUG_INFO_ROOT@|.|' plugInfo.json
echo "generated $(grep -c '^class ' generatedSchema.usda) schemas"
