"""Tests for security module."""

from harnessgenj_dev.executor.security import SecurityLevel, check_dangerous_command, is_safe_to_run


class TestSecurityChecks:
    """Test dangerous pattern detection."""

    def test_safe_code(self):
        """Simple print should be safe."""
        code = "print('hello')"
        safe, reason = is_safe_to_run(code)
        assert safe is True

    def test_safe_math(self):
        """Basic math should be safe."""
        code = "result = 2 + 2\nprint(result)"
        safe, reason = is_safe_to_run(code)
        assert safe is True

    def test_dangerous_rm_rf(self):
        """rm -rf / should be blocked at all levels."""
        code = "import os; os.system('rm -rf /')"
        safe, reason = is_safe_to_run(code)
        assert safe is False

    def test_dangerous_eval_strict(self):
        """eval should be blocked at STRICT level."""
        code = "eval('__import__(\"os\").system(\"rm -rf /\")')"
        safe, reason = is_safe_to_run(code, level=SecurityLevel.STRICT)
        assert safe is False

    def test_dangerous_exec_strict(self):
        """exec should be blocked at STRICT level."""
        code = "exec('import os')"
        safe, reason = is_safe_to_run(code, level=SecurityLevel.STRICT)
        assert safe is False

    def test_pickle_allowed_at_moderate(self):
        """pickle is not blocked at MODERATE level (not in pattern list)."""
        code = "import pickle; pickle.loads(data)"
        safe, reason = is_safe_to_run(code, level=SecurityLevel.MODERATE)
        # pickle is not in the destructive or dynamic_code patterns
        assert safe is True

    def test_shutil_rmtree_root_blocked(self):
        """shutil.rmtree on root should be blocked."""
        code = "import shutil; shutil.rmtree('/')"
        safe, reason = is_safe_to_run(code)
        assert safe is False


class TestSecurityLevels:
    """Test different security levels."""

    def test_strict_blocks_more(self):
        """Strict level should block more patterns than moderate."""
        code = "import socket; s = socket.socket()"
        safe_strict, _ = is_safe_to_run(code, level=SecurityLevel.STRICT)
        safe_moderate, _ = is_safe_to_run(code, level=SecurityLevel.MODERATE)
        assert safe_strict is False  # Network blocked in strict
        assert safe_moderate is True  # Network allowed in moderate

    def test_permissive_allows_most(self):
        """Permissive should only block destructive patterns."""
        code = "import os; os.listdir('/tmp')"
        safe_strict, _ = is_safe_to_run(code, level=SecurityLevel.STRICT)
        safe_permissive, _ = is_safe_to_run(code, level=SecurityLevel.PERMISSIVE)
        assert safe_strict is False  # Filesystem blocked in strict
        assert safe_permissive is True  # Only destructive blocked in permissive

    def test_destructive_always_blocked(self):
        """Destructive patterns should be blocked at all levels."""
        code = "rm -rf /"
        for level in [SecurityLevel.STRICT, SecurityLevel.MODERATE, SecurityLevel.PERMISSIVE]:
            safe, _ = is_safe_to_run(code, level=level)
            assert safe is False, f"Should be blocked at {level}"


class TestCheckDangerousCommand:
    """Test pattern matching directly."""

    def test_no_dangerous_patterns(self):
        """Clean code should have no matches."""
        code = "x = 1 + 1"
        found = check_dangerous_command(code)
        assert found == []

    def test_finds_destructive_pattern(self):
        """Should find destructive pattern."""
        code = "sudo rm -rf /"
        found = check_dangerous_command(code)
        assert len(found) >= 1
        assert "destructive" in found[0]
