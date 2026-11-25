#!/bin/bash
# Make the workspace's addons loadable: external addons from repo_deps.yaml,
# then their Python dependencies. Shared by the install job and every test shard,
# since each runs in a fresh container.
set -exo pipefail

uv pip install pyyaml
python3 .github/ci/clone_deps.py
EXCLUDE=$(grep '^EXCLUDE=' "${GITHUB_ENV}" | tail -1 | cut -d= -f2-)

PYTHON_DEPS=$(manifestoo --select-addons-dir "${GITHUB_WORKSPACE}" --select-exclude "${EXCLUDE}" list-external-dependencies python)
if [ -n "${PYTHON_DEPS}" ]; then
  uv pip install ${PYTHON_DEPS}
fi

find "${GITHUB_WORKSPACE}" -mindepth 2 -maxdepth 2 -name test-requirements.txt -print0 | \
  xargs -0 -r -I {} uv pip install -r {}
