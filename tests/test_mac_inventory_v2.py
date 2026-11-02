import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "mac_inventory_v2.py"
spec = importlib.util.spec_from_file_location("mac_inventory_v2", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BundleDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def app(self, name, bundle_id, version="2026.1"):
        bundle = self.root / name
        (bundle / "Contents").mkdir(parents=True)
        with (bundle / "Contents" / "Info.plist").open("wb") as stream:
            plistlib.dump({"CFBundleIdentifier": bundle_id,
                           "CFBundleShortVersionString": version,
                           "CFBundleVersion": "1234"}, stream)
        return bundle

    def test_codex_chatgpt_new_app_is_detected(self):
        self.app("ChatGPT.app", "com.openai.codex")
        result, query = module.discover_apps([self.root], use_spotlight=False)
        self.assertEqual(query, "SKIPPED")
        self.assertEqual(len(result["codex_desktop"]), 1)
        self.assertEqual(result["codex_desktop"][0]["short_version"], "2026.1")

    def test_classic_chatgpt_is_not_misidentified(self):
        self.app("ChatGPT Classic.app", "com.openai.chat")
        result, _ = module.discover_apps([self.root], use_spotlight=False)
        self.assertEqual(result["codex_desktop"], [])

    def test_claude_desktop_detected(self):
        self.app("Claude.app", "com.anthropic.claudefordesktop")
        result, _ = module.discover_apps([self.root], use_spotlight=False)
        self.assertTrue(result["claude_desktop"])

    def test_codex_legacy_bundle_detected(self):
        self.app("Codex.app", "com.openai.codex")
        result, _ = module.discover_apps([self.root], use_spotlight=False)
        self.assertTrue(result["codex_desktop"])

    def test_plist_wrong_bundle_id_is_rejected(self):
        path = self.app("Codex.app", "com.fake.codex")
        self.assertIsNone(module.bundle_info(path))

    def test_invalid_plist_fails_safely(self):
        path = self.root / "ChatGPT.app" / "Contents"
        path.mkdir(parents=True)
        (path / "Info.plist").write_text("invalid")
        self.assertIsNone(module.bundle_info(path.parent))

    def test_no_upgrade_to_enforced_by_discovery(self):
        self.app("ChatGPT.app", "com.openai.codex")
        result = module.report(roots=[self.root], use_spotlight=False)
        self.assertEqual(result["G2"], "BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED")
        self.assertFalse(result["enforced_available"])
        self.assertTrue(result["providers"]["codex_desktop"]["app_bundle_detected"])
        self.assertEqual(result["providers"]["codex_desktop"]["mandatory_write_boundary"], "NOT_TESTED")

    def test_no_report_file_written_without_request(self):
        self.app("ChatGPT.app", "com.openai.codex")
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        module.report(roots=[self.root], use_spotlight=False)
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
