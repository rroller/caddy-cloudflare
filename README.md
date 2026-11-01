# Minimal Caddy with Cloudflare DNS

A personal Caddy image built from the official Caddy images, with **only**
[`caddy-dns/cloudflare`](https://github.com/caddy-dns/cloudflare) added.
No home configuration, certificates, passwords or DNS tokens are included.
This repository is independently maintained and is not an official Caddy distribution.

## Use on Unraid

Set the container's Repository to:

```text
ghcr.io/rroller/caddy-cloudflare:2
```

Keep your existing `/etc/caddy/Caddyfile`, `/data` and `/config` mappings and
your Cloudflare token environment variable. Remove any `/usr/bin/caddy` mapping:
the executable comes from the image. Unraid can then check and pull updates normally.
Publishing an image does not automatically restart or update your Unraid container;
use Unraid's normal update controls or an updater you separately configure.

Images target **linux/amd64**, matching the intended Unraid server.
The repository and container package must both be public for anonymous pulls.
GitHub initially creates container packages as private: after the first publish,
open the package's settings and change its visibility to public once.

## Automatic builds

GitHub Actions checks daily at 10:23 UTC, on pushes to `main`, and on manual runs.
It selects the latest stable **Caddy 2** release and the latest stable tagged
Cloudflare module, then pulls the official builder/runtime images. Their exact
digests and this repository's commit form a fingerprint. If the published `:2`
image already has the same fingerprint, the run skips the build and publish.
Base image fixes therefore trigger a rebuild even without a Caddy version change.

When inputs change the workflow:

1. Pins both official base images by digest and the module by version for that build.
2. Builds the image and checks the actual Caddy and module versions.
3. Confirms exactly one nonstandard module and validates a wildcard DNS configuration
   with a dummy token and networking disabled.
4. Publishes the **tested image** to GHCR using the repository's `GITHUB_TOKEN`.
5. Creates a GitHub build provenance attestation and uploads build metadata.

Tags: `:2`, `:latest`, `:2.MINOR`, `:2.MINOR.PATCH`, plus a unique
`:build-RUN_ID-ATTEMPT` tag for rollback. Version tags can move when a module
or base image changes. Use the unique build tag or digest to pin an exact image.
Failed builds or validation do not replace the published image. A publication
or attestation failure marks the workflow failed; already-pushed tags may exist.

No Cloudflare credentials, access to the home network, or long-lived registry
password is needed by CI. Actions are pinned to commits; Dependabot proposes
updates. Pull requests build and validate without publishing. Automated updates
still trust GitHub Actions, official Caddy images, Go's module infrastructure,
and the upstream Caddy and Cloudflare module maintainers.

GitHub can delay scheduled runs and can disable schedules in inactive public
repositories after 60 days. Check the Actions page if builds stop, and re-enable
the workflow if GitHub disables it. This is not an unattended deployment system.

## Manual build and verification

With Docker, Git and Python 3 installed:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build.py
# Tested local image: caddy-build-test:local
```

For the versions directly specified in the Dockerfile (without automatic resolution):

```sh
docker build --pull -t caddy-cloudflare:local .
```

Resolve a published digest and verify its GitHub attestation:

```sh
docker buildx imagetools inspect ghcr.io/rroller/caddy-cloudflare:2
gh attestation verify oci://ghcr.io/rroller/caddy-cloudflare:2 --repo rroller/caddy-cloudflare
```

Build details are in each successful workflow's `build-info` artifact. Preserve
`caddy`, `cloudflare`, `builder`, `runtime`, and `revision` from that file to
rebuild the same source inputs. Attestations identify the GitHub build; they
are not an independent security audit.
