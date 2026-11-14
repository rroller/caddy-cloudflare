#!/usr/bin/env python3
"""Resolve, build, test and optionally publish the minimal Caddy image."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
INPUT_LABEL = 'io.github.caddy-cloudflare.build-inputs'


def fetch_json(url):
    headers = {'User-Agent': 'minimal-caddy-builder', 'Accept': 'application/json'}
    token = os.environ.get('GH_TOKEN')
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.load(r)


def latest_caddy(releases):
    versions = []
    for release in releases:
        match = re.fullmatch(r'v(2\.\d+\.\d+)', release.get('tag_name', ''))
        if match and not release.get('prerelease') and not release.get('draft'):
            versions.append(match.group(1))
    if not versions:
        raise ValueError('No stable Caddy 2 release found')
    return max(versions, key=lambda v: tuple(map(int, v.split('.'))))


def module_version(data):
    version = data['Version']
    if not re.fullmatch(r'v\d+\.\d+\.\d+', version):
        raise ValueError('Expected a stable tagged Cloudflare module release')
    return version


def run(*args, capture=False, check=True):
    return subprocess.run(args, cwd=ROOT, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None)


def inspect_image(image):
    return json.loads(run('docker', 'image', 'inspect', image, capture=True).stdout)[0]


def base_digest(image):
    run('docker', 'pull', image)
    return inspect_image(image)['RepoDigests'][0]


def set_outputs(**values):
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as f:
            for key, value in values.items():
                f.write(f'{key}={value}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='local/caddy-cloudflare')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--dockerfile-defaults', action='store_true',
                        help='Build the exact versions pinned in Dockerfile')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9./_-]+', args.image):
        parser.error('Use a lowercase image repository without a tag')
    os.chdir(ROOT)
    if args.dockerfile_defaults:
        defaults = dict(re.findall(r'^ARG (\w+)=(.+)$', (ROOT / 'Dockerfile').read_text(), re.MULTILINE))
        caddy = latest_caddy([{'tag_name': 'v' + defaults['CADDY_VERSION']}])
        cloudflare = module_version({'Version': defaults['CLOUDFLARE_VERSION']})
        if defaults['CADDY_BUILDER_IMAGE'] != f'caddy:{caddy}-builder' or defaults['CADDY_RUNTIME_IMAGE'] != f'caddy:{caddy}':
            raise ValueError('Dockerfile base images must match CADDY_VERSION')
    else:
        caddy = latest_caddy(fetch_json('https://api.github.com/repos/caddyserver/caddy/releases?per_page=100'))
        cloudflare = module_version(fetch_json('https://proxy.golang.org/github.com/caddy-dns/cloudflare/@latest'))
    revision = os.environ.get('GITHUB_SHA') or run('git', 'rev-parse', 'HEAD', capture=True).stdout.strip()
    inputs = {
        'caddy': caddy,
        'cloudflare': cloudflare,
        'builder': base_digest(f'caddy:{caddy}-builder'),
        'runtime': base_digest(f'caddy:{caddy}'),
        'revision': revision,
    }
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    info = {**inputs, 'input_hash': fingerprint}
    target = args.image + ':2'
    if args.publish:
        # A missing first image is expected; other build/publish failures still fail CI.
        previous = run('docker', 'pull', target, check=False)
        if previous.returncode == 0:
            labels = inspect_image(target)['Config'].get('Labels') or {}
            if labels.get(INPUT_LABEL) == fingerprint:
                print('Upstream versions, base digests and source revision are unchanged.')
                Path('build-info.json').write_text(json.dumps({**info, 'unchanged': True}, indent=2) + '\n')
                set_outputs(published='false')
                return
    local = 'caddy-build-test:local'
    source = 'https://github.com/' + os.environ.get('GITHUB_REPOSITORY', 'rroller/caddy-cloudflare')
    run('docker', 'build', '--pull', '--no-cache',
        '--build-arg', f'CADDY_VERSION={caddy}',
        '--build-arg', f'CLOUDFLARE_VERSION={cloudflare}',
        '--build-arg', f'CADDY_BUILDER_IMAGE={inputs["builder"]}',
        '--build-arg', f'CADDY_RUNTIME_IMAGE={inputs["runtime"]}',
        '--label', f'{INPUT_LABEL}={fingerprint}',
        '--label', f'org.opencontainers.image.source={source}',
        '--label', f'org.opencontainers.image.revision={revision}',
        '--label', f'org.opencontainers.image.version={caddy}',
        '--label', 'org.opencontainers.image.description=Caddy with only the Cloudflare DNS module',
        '--tag', local, '.')
    version = run('docker', 'run', '--rm', '--network', 'none', local,
                  'caddy', 'version', capture=True).stdout.strip()
    if version.split()[0] != 'v' + caddy:
        raise RuntimeError('Built Caddy version does not match the selected release')
    modules = run('docker', 'run', '--rm', '--network', 'none', local,
                  'caddy', 'list-modules', '--versions', capture=True).stdout
    expected_module = f'dns.providers.cloudflare {cloudflare}'
    if expected_module not in modules.splitlines() or not re.search(r'Non-standard modules:\s+1\b', modules):
        raise RuntimeError('Expected exactly one custom module at the selected version')
    run('docker', 'run', '--rm', '--network', 'none', '--read-only',
        '--tmpfs', '/data', '--tmpfs', '/config', '--tmpfs', '/tmp',
        # Syntactically valid but deliberately fake; validation has no network.
        '--env', 'CLOUDFLARE_API_TOKEN=' + '0' * 40,
        '--mount', f'type=bind,src={ROOT / "tests/Caddyfile"},dst=/etc/caddy/Caddyfile,readonly',
        local, 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
    info.update(version_output=version, modules=modules, tested=True,
                built_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if args.publish:
        # Publish only the exact local image which passed all checks.
        run_tag = f'build-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
        tags = [run_tag, caddy, '.'.join(caddy.split('.')[:2]), '2', 'latest']
        for tag in tags:
            tagged = args.image + ':' + tag
            run('docker', 'tag', local, tagged)
            run('docker', 'push', tagged)
        digests = inspect_image(args.image + ':' + run_tag)['RepoDigests']
        digest = next(d.split('@', 1)[1] for d in digests if d.split('@', 1)[0] == args.image)
        info.update(image=args.image, digest=digest, tags=tags)
        set_outputs(published='true', image=args.image, digest=digest)
    Path('build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    print(json.dumps({k: v for k, v in info.items() if k != 'modules'}, indent=2))


if __name__ == '__main__':
    main()
