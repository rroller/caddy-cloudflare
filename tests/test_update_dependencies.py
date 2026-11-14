import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from update_dependencies import update_dockerfile


class DependencyUpdates(unittest.TestCase):
    def setUp(self):
        self.original = ('ARG CADDY_BUILDER_IMAGE=caddy:2.11.7-builder\n'
                         'ARG CADDY_RUNTIME_IMAGE=caddy:2.11.7\n'
                         'ARG CADDY_VERSION=2.11.7\n'
                         'ARG CLOUDFLARE_VERSION=v0.2.4\n'
                         'FROM ${CADDY_BUILDER_IMAGE} AS builder\n')

    def test_updates_both_dependencies_and_is_idempotent(self):
        updated = update_dockerfile(self.original, '2.11.9', 'v0.3.0')
        self.assertEqual(updated, self.original.replace('2.11.7', '2.11.9').replace('v0.2.4', 'v0.3.0'))
        self.assertEqual(update_dockerfile(updated, '2.11.9', 'v0.3.0'), updated)

    def test_rejects_downgrades(self):
        for caddy, module in [('2.11.6', 'v0.2.4'), ('2.11.9', 'v0.2.3')]:
            with self.subTest(caddy=caddy, module=module), self.assertRaises(ValueError):
                update_dockerfile(self.original, caddy, module)

    def test_rejects_missing_or_duplicate_defaults(self):
        for text in [self.original.replace('ARG CADDY_VERSION=2.11.7\n', ''),
                     self.original + 'ARG CADDY_VERSION=2.11.7\n']:
            with self.assertRaises(ValueError):
                update_dockerfile(text, '2.11.9', 'v0.2.4')

    def test_rejects_unstable_versions(self):
        for caddy, module in [('3.0.0', 'v0.2.4'), ('2.12.0-rc.1', 'v0.2.4'),
                              ('2.11.9', 'v0.3.0-rc.1')]:
            with self.subTest(caddy=caddy, module=module), self.assertRaises(ValueError):
                update_dockerfile(self.original, caddy, module)
