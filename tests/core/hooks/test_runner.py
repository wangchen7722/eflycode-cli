"""HookRunner 测试"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from eflycode.core.hooks.runner import HookRunner
from eflycode.core.hooks.types import CommandHook, HookEventName


class TestHookRunner(unittest.TestCase):
    """HookRunner 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir)
        self.runner = HookRunner(workspace_dir=self.workspace_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_hook_success(self):
        """测试成功执行 hook"""
        hook = CommandHook(name="test", command="echo 'test output'")
        result = self.runner.execute_hook(
            hook, HookEventName.BEFORE_TOOL, {"tool_name": "test"}, session_id="test_session"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test output", result.stdout)

    def test_execute_hook_with_json_output(self):
        """测试执行返回 JSON 的 hook"""
        hook = CommandHook(
            name="test",
            command="echo '{\"decision\": \"allow\", \"continue\": true}'",
        )
        result = self.runner.execute_hook(
            hook, HookEventName.BEFORE_TOOL, {"tool_name": "test"}, session_id="test_session"
        )
        self.assertTrue(result.success)
        self.assertIn("decision", result.stdout)

    def test_execute_hook_timeout(self):
        """测试 hook 超时"""
        # 使用 sleep 命令测试超时（如果系统支持）
        import platform

        if platform.system() != "Windows":
            hook = CommandHook(name="test", command="sleep 2", timeout=500)  # 500ms 超时
            result = self.runner.execute_hook(
                hook,
                HookEventName.BEFORE_TOOL,
                {"tool_name": "test"},
                session_id="test_session",
            )
            self.assertFalse(result.success)
            self.assertIn("timeout", result.stderr.lower())

    def test_execute_hook_with_env_vars(self):
        """测试 hook 环境变量"""
        hook = CommandHook(name="test", command="echo $EFLYCODE_PROJECT_DIR")
        result = self.runner.execute_hook(
            hook, HookEventName.BEFORE_TOOL, {"tool_name": "test"}, session_id="test_session"
        )
        self.assertTrue(result.success)
        self.assertIn(str(self.workspace_dir), result.stdout)

    def test_execute_hooks_parallel(self):
        """测试并行执行 hooks"""
        hook1 = CommandHook(name="hook1", command="echo 'hook1'")
        hook2 = CommandHook(name="hook2", command="echo 'hook2'")
        results = self.runner.execute_hooks_parallel(
            [hook1, hook2],
            HookEventName.BEFORE_TOOL,
            {"tool_name": "test"},
            session_id="test_session",
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

    def test_execute_hooks_sequential(self):
        """测试串行执行 hooks"""
        # 创建一个临时脚本，将输入追加到文件
        script_path = self.workspace_dir / "test_script.sh"
        script_path.write_text("#!/bin/bash\nread input\necho \"$input\" > /tmp/hook_output.txt\necho '{\"hookSpecificOutput\": {\"key\": \"value\"}}'")
        script_path.chmod(0o755)

        hook1 = CommandHook(name="hook1", command=f"bash {script_path}")
        hook2 = CommandHook(name="hook2", command="echo 'hook2'")
        results = self.runner.execute_hooks_sequential(
            [hook1, hook2],
            HookEventName.BEFORE_TOOL,
            {"tool_name": "test"},
            session_id="test_session",
        )
        self.assertEqual(len(results), 2)

    def test_build_input_data(self):
        """测试构造输入数据"""
        input_data = self.runner._build_input_data(
            HookEventName.BEFORE_TOOL,
            {"tool_name": "test"},
            "test_session",
            self.workspace_dir,
        )
        self.assertEqual(input_data["hook_event_name"], "BeforeTool")
        self.assertEqual(input_data["session_id"], "test_session")
        self.assertEqual(input_data["tool_name"], "test")
        self.assertIn("timestamp", input_data)

    def test_expand_env_vars(self):
        """测试环境变量展开"""
        command = "$EFLYCODE_PROJECT_DIR/test.sh"
        expanded = self.runner._expand_env_vars(command, self.workspace_dir, "test_session")
        self.assertIn(str(self.workspace_dir), expanded)
        self.assertNotIn("$EFLYCODE_PROJECT_DIR", expanded)

    def test_prepare_environment(self):
        """测试准备环境变量"""
        env = self.runner._prepare_environment(self.workspace_dir, "test_session")
        self.assertEqual(env["EFLYCODE_PROJECT_DIR"], str(self.workspace_dir))
        self.assertEqual(env["EFLYCODE_SESSION_ID"], "test_session")
        self.assertIn("EFLYCODE_CLI_VERSION", env)


if __name__ == "__main__":
    unittest.main()

