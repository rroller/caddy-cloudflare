import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('build', Path(__file__).parents[1] / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class VersionSelection(unittest.TestCase):
    def test_ignores_prereleases_drafts_and_other_major_versions(self):
        releases = [{'tag_name': 'v2.11.7'}, {'tag_name': 'v3.0.0'},
                    {'tag_name': 'v2.12.0-rc.1'},
                    {'tag_name': 'v2.12.0', 'prerelease': True},
                    {'tag_name': 'v2.13.0', 'draft': True}]
        self.assertEqual(build.latest_caddy(releases), '2.11.7')

    def test_semantic_not_lexical_order(self):
        self.assertEqual(build.latest_caddy([{'tag_name': 'v2.9.9'},
                                             {'tag_name': 'v2.11.7'}]), '2.11.7')

    def test_rejects_missing_stable_release(self):
        with self.assertRaises(ValueError):
            build.latest_caddy([{'tag_name': 'v2.12.0-rc.1'}])

    def test_module_requires_stable_tag(self):
        self.assertEqual(build.module_version({'Version': 'v0.2.4'}), 'v0.2.4')
        for version in ['v0.3.0-rc.1', 'v0.0.0-20260101000000-deadbeef', 'latest', 'v0.2.4;echo bad']:
            with self.subTest(version=version), self.assertRaises(ValueError):
                build.module_version({'Version': version})


if __name__ == '__main__':
    unittest.main()
