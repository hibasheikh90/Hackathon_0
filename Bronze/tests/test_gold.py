"""
Gold Tier — End-to-End Test Suite
===================================
Comprehensive tests for all Gold Tier modules.

Run:
    python tests/test_gold.py
    python -m pytest tests/test_gold.py -v   (if pytest installed)
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ===================================================================
# 1. Core Infrastructure
# ===================================================================

class TestEventBus(unittest.TestCase):
    """Test core/event_bus.py"""

    def setUp(self):
        from core.event_bus import EventBus
        self.bus = EventBus()

    def test_subscribe_and_emit(self):
        results = []
        self.bus.on("test.event", lambda d: results.append(d))
        self.bus.emit("test.event", {"key": "value"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "value")

    def test_wildcard_handler(self):
        results = []
        self.bus.on("odoo.*", lambda d: results.append(d))
        self.bus.emit("odoo.invoice.created", {"id": 1})
        self.assertEqual(len(results), 1)

    def test_unsubscribe(self):
        results = []
        handler = lambda d: results.append(d)
        self.bus.on("test.unsub", handler)
        self.bus.off("test.unsub", handler)
        self.bus.emit("test.unsub", {})
        self.assertEqual(len(results), 0)

    def test_handler_exception_caught(self):
        def bad_handler(d):
            raise ValueError("boom")
        self.bus.on("test.error", bad_handler)
        record = self.bus.emit("test.error", {})
        self.assertEqual(len(record.errors), 1)
        self.assertIn("boom", record.errors[0])

    def test_history_tracking(self):
        self.bus.emit("a", {})
        self.bus.emit("b", {})
        self.assertEqual(len(self.bus.history), 2)

    def test_handlers_for(self):
        handler = lambda d: None
        self.bus.on("test.lookup", handler)
        self.assertIn(handler, self.bus.handlers_for("test.lookup"))

    def test_clear(self):
        self.bus.on("test.clear", lambda d: None)
        self.bus.emit("test.clear", {})
        self.bus.clear()
        self.assertEqual(len(self.bus.history), 0)
        self.assertEqual(len(self.bus.handlers_for("test.clear")), 0)


class TestErrorLogger(unittest.TestCase):
    """Test core/error_logger.py"""

    def setUp(self):
        from core.error_logger import ErrorLogger
        self.log_dir = _PROJECT_ROOT / "logs" / "_test"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = ErrorLogger(
            error_log=self.log_dir / "error.log",
            audit_log=self.log_dir / "audit.log",
            archive_dir=self.log_dir / "archive",
            alert_threshold=3,
            alert_window_seconds=3600,
        )

    def tearDown(self):
        import shutil
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir)

    def test_log_error(self):
        rec = self.logger.log_error("test", ValueError("fail"), {"ctx": 1})
        self.assertEqual(rec["source"], "test")
        self.assertEqual(rec["severity"], "ERROR")
        self.assertTrue((self.log_dir / "error.log").is_file())

    def test_log_audit(self):
        rec = self.logger.log_audit("test.action", "success", {"x": 1})
        self.assertEqual(rec["action"], "test.action")
        self.assertTrue((self.log_dir / "audit.log").is_file())

    def test_recent_errors(self):
        self.logger.log_error("src", "e1")
        self.logger.log_error("src", "e2")
        errors = self.logger.recent_errors(5)
        self.assertEqual(len(errors), 2)

    def test_alert_escalation(self):
        from core.event_bus import EventBus
        bus = EventBus()
        self.logger.set_event_bus(bus)
        alerts = []
        bus.on("error.alert_triggered", lambda d: alerts.append(d))

        for i in range(3):
            self.logger.log_error("spike.source", f"error {i}")

        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["source"], "spike.source")

    def test_rotation(self):
        # Write enough to trigger size-based rotation
        self.logger._max_file_bytes = 100  # tiny threshold
        for i in range(20):
            self.logger.log_error("rot", f"error {i}")
        archived = self.logger.rotate_if_needed()
        self.assertGreater(len(archived), 0)


class TestConfigLoader(unittest.TestCase):
    """Test core/config_loader.py"""

    def test_load(self):
        from core.config_loader import config
        config.load()
        self.assertIsNotNone(config.scheduler)
        self.assertIsInstance(config.scheduler, dict)

    def test_get_dotted(self):
        from core.config_loader import config
        config.load()
        val = config.get("scheduler.vault_scan_interval_min")
        self.assertEqual(val, 5)

    def test_get_default(self):
        from core.config_loader import config
        config.load()
        val = config.get("nonexistent.key", default="fallback")
        self.assertEqual(val, "fallback")

    def test_section(self):
        from core.config_loader import config
        config.load()
        s = config.section("error_logging")
        self.assertIn("alert_threshold", s)

    def test_properties(self):
        from core.config_loader import config
        config.load()
        self.assertIsInstance(config.social_accounts, dict)
        self.assertIsInstance(config.odoo, dict)
        self.assertIsInstance(config.briefing, dict)


# ===================================================================
# 2. Integrations
# ===================================================================

class TestSocialBase(unittest.TestCase):
    """Test integrations/social/base.py"""

    def test_post_result_dataclass(self):
        from integrations.social.base import PostResult
        r = PostResult(success=True, platform="test", post_id="123")
        self.assertTrue(r.success)
        self.assertEqual(r.platform, "test")
        self.assertIsNotNone(r.timestamp)

    def test_metrics_result(self):
        from integrations.social.base import MetricsResult
        m = MetricsResult(platform="twitter", post_id="456", impressions=1000, likes=50)
        self.assertEqual(m.engagement_rate, 5.0)  # 50/1000*100

    def test_validate_content_empty(self):
        from integrations.social.linkedin import LinkedInPlatform
        li = LinkedInPlatform()
        self.assertIsNotNone(li.validate_content(""))

    def test_validate_content_ok(self):
        from integrations.social.twitter import TwitterPlatform
        tw = TwitterPlatform()
        self.assertIsNone(tw.validate_content("Hello world"))

    def test_validate_content_too_long(self):
        from integrations.social.twitter import TwitterPlatform
        tw = TwitterPlatform()
        self.assertIsNotNone(tw.validate_content("x" * 281))


class TestContentQueue(unittest.TestCase):
    """Test integrations/social/content_queue.py"""

    def setUp(self):
        self.test_dir = _PROJECT_ROOT / "tests" / "_test_queue"
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_parse_frontmatter(self):
        from integrations.social.content_queue import _parse_frontmatter
        content = "---\nplatforms: linkedin, twitter\nstatus: draft\n---\nHello world"
        meta, body = _parse_frontmatter(content)
        self.assertEqual(meta["platforms"], ["linkedin", "twitter"])
        self.assertEqual(meta["status"], "draft")
        self.assertEqual(body, "Hello world")

    def test_write_frontmatter(self):
        from integrations.social.content_queue import _write_frontmatter
        result = _write_frontmatter({"status": "draft", "platforms": ["linkedin"]}, "Content")
        self.assertIn("---", result)
        self.assertIn("status: draft", result)
        self.assertIn("Content", result)

    def test_queue_lifecycle(self):
        from integrations.social.content_queue import ContentQueue, _write_frontmatter

        # Write a test draft
        draft = self.test_dir / "social_test.md"
        draft.write_text(_write_frontmatter(
            {"platforms": "linkedin", "status": "approved"},
            "Test content",
        ), encoding="utf-8")

        queue = ContentQueue(queue_dir=self.test_dir)
        items = queue.scan()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "approved")
        self.assertTrue(items[0].is_ready)


class TestSocialScheduler(unittest.TestCase):
    """Test integrations/social/scheduler.py"""

    def test_can_post(self):
        from integrations.social.scheduler import SocialScheduler
        sched = SocialScheduler()
        self.assertTrue(sched.can_post("linkedin"))

    def test_next_optimal_slot(self):
        from integrations.social.scheduler import SocialScheduler
        sched = SocialScheduler()
        slot = sched.next_optimal_slot("twitter")
        self.assertIsNotNone(slot)
        self.assertIsInstance(slot, datetime)


# ===================================================================
# 3. Data Collectors
# ===================================================================

class TestDataCollectors(unittest.TestCase):
    """Test briefings/data_collectors/*"""

    def test_vault_stats(self):
        from briefings.data_collectors.vault_stats import collect
        data = collect()
        self.assertIn("inbox_count", data)
        self.assertIn("backlog", data)
        self.assertIn("high_priority_items", data)

    def test_financial_summary(self):
        from briefings.data_collectors.financial_summary import collect
        data = collect()
        self.assertIn("available", data)  # False when Odoo not connected

    def test_social_metrics(self):
        from briefings.data_collectors.social_metrics import collect
        data = collect()
        self.assertIn("platforms", data)
        self.assertIn("total_posts", data)

    def test_email_digest(self):
        from briefings.data_collectors.email_digest import collect
        data = collect()
        self.assertIn("emails_received", data)
        self.assertIn("emails_sent", data)
        self.assertIn("key_threads", data)


# ===================================================================
# 4. Weekly CEO Briefing
# ===================================================================

class TestWeeklyBriefing(unittest.TestCase):
    """Test briefings/weekly_ceo.py"""

    def test_generate_stdout(self):
        from briefings.weekly_ceo import generate_briefing
        # stdout_only=True should return None and not write a file
        result = generate_briefing(stdout_only=True)
        self.assertIsNone(result)

    def test_collect_all(self):
        from briefings.weekly_ceo import _collect_all
        data = _collect_all()
        self.assertIn("vault", data)
        self.assertIn("financials", data)
        self.assertIn("social", data)
        self.assertIn("email", data)

    def test_executive_summary(self):
        from briefings.weekly_ceo import _build_executive_summary
        data = {
            "vault": {"done_this_week": 10, "new_this_week": 5, "backlog": 3},
            "financials": {"available": False},
            "social": {"total_posts": 2},
            "action_items": [],
        }
        summary = _build_executive_summary(data)
        self.assertIn("10", summary)
        self.assertIn("2 social", summary)


# ===================================================================
# 5. MCP Servers
# ===================================================================

class TestMCPServers(unittest.TestCase):
    """Test that all MCP servers register their tools correctly."""

    def _get_tools(self, server):
        return asyncio.run(server.list_tools())

    def test_vault_server(self):
        from mcp_servers.vault_server import mcp
        tools = self._get_tools(mcp)
        names = [t.name for t in tools]
        self.assertIn("vault_status", names)
        self.assertIn("list_tasks", names)
        self.assertIn("search_vault", names)

    def test_email_server(self):
        from mcp_servers.email_server import mcp
        tools = self._get_tools(mcp)
        names = [t.name for t in tools]
        self.assertIn("send_email", names)
        self.assertIn("check_inbox", names)

    def test_accounting_server(self):
        from mcp_servers.accounting_server import mcp
        tools = self._get_tools(mcp)
        names = [t.name for t in tools]
        self.assertIn("get_unpaid_invoices", names)
        self.assertIn("get_profit_loss", names)
        self.assertIn("get_cash_position", names)

    def test_social_server(self):
        from mcp_servers.social_server import mcp
        tools = self._get_tools(mcp)
        names = [t.name for t in tools]
        self.assertIn("create_draft", names)
        self.assertIn("post_now", names)
        self.assertIn("post_multi", names)
        self.assertIn("process_queue", names)
        self.assertIn("get_rate_limits", names)
        self.assertIn("engagement_summary", names)
        self.assertIn("get_post_history", names)

    def test_briefing_server(self):
        from mcp_servers.briefing_server import mcp
        tools = self._get_tools(mcp)
        names = [t.name for t in tools]
        self.assertIn("generate_weekly_briefing", names)
        self.assertIn("get_last_briefing", names)

    def test_total_tool_count(self):
        """Verify we have 30 total tools across all servers."""
        from mcp_servers.vault_server import mcp as v
        from mcp_servers.email_server import mcp as e
        from mcp_servers.accounting_server import mcp as a
        from mcp_servers.social_server import mcp as s
        from mcp_servers.briefing_server import mcp as b

        total = sum(
            len(self._get_tools(server))
            for server in (v, e, a, s, b)
        )
        self.assertEqual(total, 30)


# ===================================================================
# 5b. Facebook Platform & Social Automation
# ===================================================================

class TestFacebookPlatform(unittest.TestCase):
    """Test integrations/social/facebook.py"""

    def test_import(self):
        from integrations.social.facebook import FacebookPlatform
        self.assertTrue(callable(FacebookPlatform))

    def test_implements_base(self):
        from integrations.social.facebook import FacebookPlatform
        from integrations.social.base import SocialPlatform
        fb = FacebookPlatform()
        self.assertIsInstance(fb, SocialPlatform)
        self.assertEqual(fb.platform_name, "facebook")
        self.assertEqual(fb.char_limit, 63206)

    def test_validate_content_empty(self):
        from integrations.social.facebook import FacebookPlatform
        fb = FacebookPlatform()
        self.assertIsNotNone(fb.validate_content(""))

    def test_validate_content_ok(self):
        from integrations.social.facebook import FacebookPlatform
        fb = FacebookPlatform()
        self.assertIsNone(fb.validate_content("Hello from Facebook!"))


class TestSocialAutomation(unittest.TestCase):
    """Test integrations/social/automation.py"""

    def test_import(self):
        from integrations.social.automation import SocialAutomation
        self.assertTrue(callable(SocialAutomation))

    def test_init(self):
        from integrations.social.automation import SocialAutomation
        auto = SocialAutomation()
        self.assertIsNotNone(auto.scheduler)
        self.assertIsNotNone(auto.queue)
        self.assertIsInstance(auto._history, list)

    def test_engagement_summary_empty(self):
        from integrations.social.automation import SocialAutomation
        auto = SocialAutomation()
        summary = auto.generate_engagement_summary(days=1)
        self.assertIn("total_posts", summary)
        self.assertIn("by_platform", summary)
        self.assertIn("rate_limits", summary)
        self.assertIn("facebook", summary["rate_limits"])
        self.assertIn("instagram", summary["rate_limits"])

    def test_vault_log_directories(self):
        from integrations.social.automation import SOCIAL_LOG_DIR, SUMMARY_DIR
        # Directories should be under vault/Done/
        self.assertIn("Done", str(SOCIAL_LOG_DIR))
        self.assertIn("Done", str(SUMMARY_DIR))

    def test_get_platform_helper(self):
        from integrations.social.automation import _get_platform
        fb = _get_platform("facebook")
        self.assertIsNotNone(fb)
        self.assertEqual(fb.platform_name, "facebook")
        ig = _get_platform("instagram")
        self.assertIsNotNone(ig)
        self.assertEqual(ig.platform_name, "instagram")
        self.assertIsNone(_get_platform("nonexistent"))


# ===================================================================
# 5c. Odoo JSON-RPC Client & Server
# ===================================================================

class TestOdooJsonRpcClient(unittest.TestCase):
    """Test integrations/odoo/jsonrpc_client.py"""

    def test_import(self):
        from integrations.odoo.jsonrpc_client import OdooJsonRpcClient, OdooConnectionError
        self.assertTrue(callable(OdooJsonRpcClient))
        self.assertTrue(issubclass(OdooConnectionError, Exception))

    def test_client_init(self):
        from integrations.odoo.jsonrpc_client import OdooJsonRpcClient
        client = OdooJsonRpcClient()
        self.assertIsNotNone(client.url)
        self.assertIsNotNone(client.db)
        self.assertIsNone(client._uid)

    def test_requires_url_and_db(self):
        from integrations.odoo.jsonrpc_client import OdooJsonRpcClient, OdooConnectionError
        client = OdooJsonRpcClient()
        original_url = client.url
        client.url = ""
        with self.assertRaises(OdooConnectionError):
            client.authenticate()
        client.url = original_url


class TestOdooJsonRpcServer(unittest.TestCase):
    """Test mcp_servers/odoo_jsonrpc_server.py"""

    def _get_tools(self, server):
        return asyncio.run(server.list_tools())

    def test_server_registers_tools(self):
        from mcp_servers.odoo_jsonrpc_server import mcp
        tools = self._get_tools(mcp)
        names = [t.name for t in tools]
        self.assertIn("create_invoice", names)
        self.assertIn("get_invoice", names)
        self.assertIn("list_unpaid_invoices", names)
        self.assertIn("list_overdue_invoices", names)
        self.assertIn("read_transactions", names)
        self.assertIn("get_customer", names)
        self.assertIn("list_customers", names)
        self.assertIn("get_account_balance", names)
        self.assertIn("log_to_vault", names)
        self.assertIn("sync_overdue_to_vault", names)

    def test_tool_count(self):
        from mcp_servers.odoo_jsonrpc_server import mcp
        tools = self._get_tools(mcp)
        self.assertEqual(len(tools), 10)

    def test_vault_log_helper(self):
        import shutil
        from mcp_servers.odoo_jsonrpc_server import _vault_log, LOG_DIR
        test_path = _vault_log("Test_Entry", "Hello world\n\n#test\n")
        self.assertTrue(test_path.exists())
        content = test_path.read_text(encoding="utf-8")
        self.assertIn("Test_Entry", content)
        self.assertIn("Hello world", content)
        # Cleanup
        test_path.unlink(missing_ok=True)

    def test_log_to_vault_tool(self):
        from mcp_servers.odoo_jsonrpc_server import log_to_vault
        result = log_to_vault(
            title="Unit Test Log",
            content="This is a test accounting note.",
            tags="#test",
        )
        self.assertEqual(result["status"], "saved")
        self.assertIn("Unit Test Log", result["file"])
        # Cleanup
        from mcp_servers.odoo_jsonrpc_server import _PROJECT_ROOT
        path = _PROJECT_ROOT / result["file"]
        path.unlink(missing_ok=True)


# ===================================================================
# 6. Validator
# ===================================================================

class TestValidator(unittest.TestCase):
    """Test core/validator.py"""

    def test_validate_all(self):
        from core.validator import validate_all
        results = validate_all()
        self.assertIn("Directories", results)
        self.assertIn("Config Files", results)
        self.assertIn("Gold Tier Modules", results)
        self.assertIn("MCP Configuration", results)

    def test_all_modules_import(self):
        from core.validator import _check_core_modules
        checks = _check_core_modules()
        failed = [c for c in checks if not c.ok]
        self.assertEqual(len(failed), 0, f"Failed imports: {failed}")


# ===================================================================
# Run
# ===================================================================

if __name__ == "__main__":
    # Suppress verbose output during tests
    import io
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
