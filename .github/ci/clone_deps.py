"""Clone the external addons listed in repo_deps.yaml and symlink them into the
workspace, then export EXCLUDE (the no_ci list) to the following steps."""
import os
import subprocess

import yaml

branch = os.environ.get('GITHUB_BASE_REF', '18.0')
workspace = os.environ.get('GITHUB_WORKSPACE', os.getcwd())

with open('repo_deps.yaml') as f:
    config = yaml.safe_load(f)

for repo_url, addons in config.get('repos', {}).items():
    clone_dir = f'/tmp/repo_{abs(hash(repo_url))}'
    result = subprocess.run(
        ['git', 'clone', '--depth=1', '-b', branch, repo_url, clone_dir],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f'Branch {branch} not found in {repo_url}, cloning default branch')
        subprocess.run(
            ['git', 'clone', '--depth=1', repo_url, clone_dir],
            check=True,
        )
    for addon in addons:
        src = os.path.join(clone_dir, addon)
        dst = os.path.join(workspace, addon)
        if os.path.isdir(src):
            os.symlink(src, dst)
            print(f'Symlinked {addon}')
        else:
            print(f'WARNING: {addon} not found in {clone_dir}')

no_ci = config.get('no_ci', [])
with open(os.environ['GITHUB_ENV'], 'a') as f:
    f.write(f"EXCLUDE={','.join(no_ci)}\n")
print(f'EXCLUDE={",".join(no_ci)}')
