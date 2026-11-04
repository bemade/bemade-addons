"""Split the post_install test classes of the repo's addons into shards.

Run with the CI image's Odoo importable, before the addons are installed (it
only imports their tests). The classes are listed with Odoo's own test loader,
so they are exactly the ones `--test-enable` would run in the post_install
phase. Each class is weighted by its duration in a previous run (--timings, as
written by class_timings.py), or by a rough estimate when it has none, and the
classes are packed into shards by longest-first greedy.

Only classes that are post_install and not at_install are sharded. A shard runs
on a restored database without -i, and Odoo would run an at_install test there
while the registry is still loading, against tables that already carry columns
of modules not loaded yet. Classes tagged both ways stay in the install job.

Writes:
- --out: the shards, a list of lists of "module:Class";
- --install-tags-out: the --test-tags for the install job, i.e. every addon
  minus the sharded classes, so anything not sharded still runs there;
- `shards` in GITHUB_OUTPUT: the shard indexes, for the test matrix.
"""
import argparse
import inspect
import json
import math
import os

# Seconds per test when a class has no recorded duration. Browser tours dominate
# (about 10 s each on the hosted runners), page-rendering HttpCase tests take
# about 1 s, and plain TransactionCase tests are cheap.
TOUR_TEST, HTTP_TEST, PLAIN_TEST, CLASS_SETUP = 9.5, 1.0, 0.3, 1.0


def is_tour(test):
    try:
        source = inspect.getsource(getattr(type(test), test._testMethodName))
    except (OSError, TypeError):
        return False
    return 'start_tour' in source or 'browser_js' in source


def discover(addons, addons_path):
    from odoo.tools import config
    config.parse_config([f'--addons-path={addons_path}', '--test-enable'])
    from odoo.tests import HttpCase, loader

    classes = {}
    for test in loader.make_suite(addons, 'post_install'):
        if 'at_install' in test.test_tags:
            continue
        key = f'{test.test_module}:{type(test).__name__}'
        if isinstance(test, HttpCase):
            cost = TOUR_TEST if is_tour(test) else HTTP_TEST
        else:
            cost = PLAIN_TEST
        classes[key] = classes.get(key, CLASS_SETUP) + cost
    return classes


def pack(weights, count):
    shards = [[] for _ in range(count)]
    loads = [0.0] * count
    for key in sorted(weights, key=lambda k: (-weights[k], k)):
        i = loads.index(min(loads))
        shards[i].append(key)
        loads[i] += weights[key]
    return shards, loads


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--addons', required=True, help='comma-separated addons to test')
    parser.add_argument('--addons-path', required=True)
    parser.add_argument('--timings', help='JSON {"module:Class": seconds} from a previous run')
    parser.add_argument('--max-shards', type=int, default=8)
    parser.add_argument('--target-seconds', type=float, default=360)
    parser.add_argument('--out', required=True)
    parser.add_argument('--install-tags-out', required=True)
    args = parser.parse_args()

    estimates = discover(args.addons.split(','), args.addons_path)
    timings = {}
    if args.timings and os.path.exists(args.timings):
        with open(args.timings) as f:
            timings = json.load(f)
    weights = {key: timings.get(key, estimate) for key, estimate in estimates.items()}
    measured = sum(1 for key in weights if key in timings)

    total = sum(weights.values())
    # No shard at all when nothing is sharded: an empty --test-tags include list
    # would make Odoo fall back to running every standard test.
    count = min(args.max_shards, max(1, math.ceil(total / args.target_seconds)), len(weights))
    shards, loads = pack(weights, count)

    print(f'{len(weights)} post_install classes ({measured} with a recorded duration), '
          f'~{total / 60:.0f} min, {count} shards')
    for i, (shard, load) in enumerate(zip(shards, loads)):
        print(f'  shard {i}: {len(shard)} classes, ~{load / 60:.1f} min')

    with open(args.out, 'w') as f:
        json.dump(shards, f)
    with open(args.install_tags_out, 'w') as f:
        f.write(','.join([f'/{addon}' for addon in args.addons.split(',')]
                         + [f'-/{key}' for key in sorted(weights)]))
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'shards={json.dumps(list(range(count)))}\n')


if __name__ == '__main__':
    main()
