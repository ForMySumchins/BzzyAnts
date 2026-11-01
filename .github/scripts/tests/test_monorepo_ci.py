"""Exercise the real dispatcher in disposable Git repositories.

Fixture hooks only record invocation; they are not application validators.
No network, third-party packages, or production schema fixtures are needed.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'monorepo-ci.sh'
COMMON = ['ants-to-bees', 'kiro-d001']
ALL = COMMON + ['node', 'python', 'tauri', 'security']


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'CI Test')
        self.git('config', 'user.email', 'ci@example.invalid')
        self.write('.git/info/exclude', '.github/ci/\ncontracts/ants-to-bees.schema.json\nhooks.log\n')
        self.write('README.md', 'baseline\n')
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True).strip()

    def write(self, path, content='changed\n'):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture', '--allow-empty')
        return self.git('rev-parse', 'HEAD')

    def hooks(self):
        self.write('contracts/ants-to-bees.schema.json', '{}\n')
        for name in ALL:
            self.write(f'.github/ci/check-{name}.sh', f'echo {name} >> hooks.log\n')

    def run_ci(self, **overrides):
        env = dict(os.environ, GH_EVENT='pull_request', PR_HEAD='fix/ci-routing',
                   PR_BASE='develop', BASE_SHA=self.base, HEAD_SHA='HEAD')
        env.update(overrides)
        (self.root / 'hooks.log').unlink(missing_ok=True)
        result = subprocess.run(['bash', str(SCRIPT)], cwd=self.root, env=env,
                                text=True, capture_output=True)
        log = self.root / 'hooks.log'
        return result, log.read_text().splitlines() if log.exists() else []

    def test_routes(self):
        # Removing a directory or extension route must lose a required hook here.
        cases = [
            ('monorepo-scaffold/apps/field-operator/index.html', ['node', 'tauri']),
            ('recovered/field-operator/src/components/geoint/observations.tsx', ['node', 'tauri']),
            ('recovered/field-operator/public/map.css', ['node', 'tauri']),
            ('recovered/legacy-poway/pipeline/h3.mjs', ['node']),
            ('recovered/legacy-poway/pipeline/data.json', ['node']),
            ('monorepo-scaffold/services/ants_api/main.py', ['python']),
            ('monorepo-scaffold/services/ingestor_core/prober/ssrf_probe.py', ['python', 'security']),
            ('monorepo-scaffold/packages/contracts/models.py', ['python']),
            ('original-spark-infer-leads/src/lead_intelligence/security/ssrf.py', ['python', 'security']),
            ('original-spark-infer-leads/pyproject.toml', ['python']),
            ('original-spark-infer-leads/tests/fixture.json', ['python']),
            ('monorepo-scaffold/package.json', ['node']),
            ('monorepo-scaffold/pnpm-workspace.yaml', ['node']),
            ('nested/package-lock.json', ['node']),
            ('nested/requirements-dev.txt', ['python']),
            ('nested/src-tauri/tauri.conf.json', ['tauri']),
            ('nested/Cargo.toml', ['tauri']),
            ('nested/contracts/fixture.json', []),
            ('kiro/design.md', []),
            ('new-component/ui/index.html', ['node']),
            ('new-component/ui/app.jsx', ['node']),
            ('new-component/lib/module.mts', ['node']),
            ('README.md', None),
            ('docs/routing.md', None),
            ('.github/scripts/tests/test_monorepo_ci.py', None),
            ('python/adapter.py', ['python']),
            ('pipeline/collect.mjs', ['node']),
            ('adapters/county/fixture.json', ['node']),
            ('apps/field-operator/index.html', ['node', 'tauri']),
            ('security/media/fixture.json', ['security']),
            ('monorepo-scaffold/new-domain/fixture.bin', ['node', 'python', 'tauri', 'security']),
        ]
        self.hooks()
        for path, domains in cases:
            with self.subTest(path=path):
                self.git('reset', '--hard', self.base)
                self.write(path)
                self.commit()
                result, hooks = self.run_ci()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(hooks, [] if domains is None else COMMON + domains)

    def test_missing_and_failing_gates(self):
        self.write('monorepo-scaffold/apps/field-operator/index.html')
        self.commit()
        result, hooks = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('schema.json is missing', result.stderr)
        self.assertEqual(hooks, [])
        self.hooks()
        for name in ALL[:3] + ['tauri']:
            with self.subTest(missing=name):
                hook = self.root / f'.github/ci/check-{name}.sh'
                content = hook.read_text()
                hook.unlink()
                result, _ = self.run_ci()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'check-{name}.sh', result.stderr)
                hook.write_text('exit 9\n')
                result, _ = self.run_ci()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('failed', result.stderr)
                hook.write_text(content)

    def test_branch_policy_even_with_no_changes(self):
        for base, head, allowed in [
            ('main', 'develop', True), ('main', 'hotfix/urgent', True),
            ('main', 'feat/new', False), ('main', 'hotfix/Bad', False),
            ('develop', 'chore/kiro-governance', True),
            ('develop', 'sec/media-quarantine', True),
            ('develop', 'feature/new', False), ('develop', 'fix/Bad', False),
            ('develop', 'fix/', False), ('develop', 'fix/a/b', False),
            ('other', 'fix/ci', False), ('develop', 'main', False),
        ]:
            with self.subTest(base=base, head=head):
                result, hooks = self.run_ci(PR_BASE=base, PR_HEAD=head)
                self.assertEqual(result.returncode == 0, allowed, result.stderr)
                self.assertEqual(hooks, [])

    def test_invalid_revisions_fail_closed(self):
        for env in [{'HEAD_SHA': 'missing'}, {'BASE_SHA': 'missing'}]:
            result, _ = self.run_ci(**env)
            self.assertNotEqual(result.returncode, 0)

    def test_initial_push_scans_entire_tree(self):
        self.write('recovered/field-operator/index.html')
        self.commit()
        result, _ = self.run_ci(GH_EVENT='push', BASE_SHA='0' * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('schema.json is missing', result.stderr)

    def test_deleted_and_renamed_source_still_validated(self):
        self.write('recovered/field-operator/index.html')
        self.base = self.commit()
        (self.root / 'docs').mkdir()
        self.git('mv', 'recovered/field-operator/index.html', 'docs/moved.md')
        self.commit()
        result, _ = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('schema.json is missing', result.stderr)

    def test_deleted_source_still_validated(self):
        self.write('recovered/field-operator/index.html')
        self.base = self.commit()
        self.git('rm', 'recovered/field-operator/index.html')
        self.commit()
        result, _ = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('schema.json is missing', result.stderr)

    def test_mixed_domains_run_all_required_hooks_once(self):
        self.write('pipeline/collect.mjs')
        self.write('original-spark-infer-leads/src/lead_intelligence/security/ssrf.py')
        self.write('apps/field-operator/index.html')
        self.commit()
        self.hooks()
        result, hooks = self.run_ci()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(hooks, ALL)
        for name in ['python', 'security']:
            self.write(f'.github/ci/check-{name}.sh', 'exit 7\n')
            result, _ = self.run_ci()
            self.assertNotEqual(result.returncode, 0)
            self.hooks()

    def test_unusual_filename_cannot_evade_routing(self):
        self.write('recovered/field-operator/odd\nname.html')
        self.commit()
        result, _ = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('schema.json is missing', result.stderr)

    def test_pr_uses_merge_base_not_unrelated_base_tip_changes(self):
        self.git('checkout', '-qb', 'base')
        self.write('unrelated.py')
        base_tip = self.commit()
        self.git('checkout', '-qb', 'feature', self.base)
        self.write('docs/feature.md')
        self.commit()
        result, hooks = self.run_ci(BASE_SHA=base_tip)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(hooks, [])


if __name__ == '__main__':
    unittest.main()
