#!/usr/bin/env python3
"""Keep Dockerfile defaults aligned with stable upstream releases."""
import re
from build import ROOT, fetch_json, latest_caddy, module_version, set_outputs


def update_dockerfile(text, caddy, cloudflare):
    if not re.fullmatch(r'2\.\d+\.\d+', caddy):
        raise ValueError('Expected a stable Caddy 2 version')
    module_version({'Version': cloudflare})
    replacements = {
        'CADDY_BUILDER_IMAGE': f'caddy:{caddy}-builder',
        'CADDY_RUNTIME_IMAGE': f'caddy:{caddy}',
        'CADDY_VERSION': caddy,
        'CLOUDFLARE_VERSION': cloudflare,
    }
    for name, value in replacements.items():
        pattern = rf'^ARG {name}=(.*)$'
        matches = re.findall(pattern, text, flags=re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one {name} default')
        old = matches[0].removeprefix('caddy:').removesuffix('-builder').removeprefix('v')
        new = value.removeprefix('caddy:').removesuffix('-builder').removeprefix('v')
        if tuple(map(int, old.split('.'))) > tuple(map(int, new.split('.'))):
            raise ValueError(f'Refusing to downgrade {name}')
        text = re.sub(pattern, f'ARG {name}={value}', text, flags=re.MULTILINE)
    return text


def main():
    caddy = latest_caddy(fetch_json('https://api.github.com/repos/caddyserver/caddy/releases?per_page=100'))
    cloudflare = module_version(fetch_json('https://proxy.golang.org/github.com/caddy-dns/cloudflare/@latest'))
    path = ROOT / 'Dockerfile'
    original = path.read_text()
    updated = update_dockerfile(original, caddy, cloudflare)
    path.write_text(updated)
    set_outputs(changed=str(updated != original).lower(), caddy=caddy, cloudflare=cloudflare)
    print(f'Caddy {caddy}; Cloudflare {cloudflare}; changed={updated != original}')


if __name__ == '__main__':
    main()
