"""Tests for HGJ roles module."""

import pytest

from harnessgenj_dev.hgj.roles import (
    HGJRole,
    DEVELOPER_ROLE,
    CODE_REVIEWER_ROLE,
    BUG_HUNTER_ROLE,
    TESTER_ROLE,
    ARCHITECT_ROLE,
    STANDARD_ROLES,
    RoleManager,
)


class TestHGJRole:
    """Test HGJRole dataclass."""

    def test_create_role(self):
        role = HGJRole(
            name="test_role",
            description="A test role",
            system_prompt="You are a tester",
        )
        assert role.name == "test_role"
        assert role.tools == []
        assert role.max_turns == 20

    def test_create_role_with_all_fields(self):
        role = HGJRole(
            name="dev",
            description="Developer",
            system_prompt="Write code",
            tools=["read_file", "write_file"],
            max_turns=30,
        )
        assert role.name == "dev"
        assert len(role.tools) == 2
        assert role.max_turns == 30


class TestStandardRoles:
    """Test standard HGJ role definitions."""

    def test_developer_role(self):
        assert DEVELOPER_ROLE.name == "developer"
        assert "software" in DEVELOPER_ROLE.system_prompt.lower()
        assert "edit_file" in DEVELOPER_ROLE.tools
        assert DEVELOPER_ROLE.max_turns == 30

    def test_code_reviewer_role(self):
        assert CODE_REVIEWER_ROLE.name == "code_reviewer"
        assert "reviewer" in CODE_REVIEWER_ROLE.system_prompt.lower()
        assert "read_file" in CODE_REVIEWER_ROLE.tools
        assert CODE_REVIEWER_ROLE.max_turns == 15

    def test_bug_hunter_role(self):
        assert BUG_HUNTER_ROLE.name == "bug_hunter"
        assert "bug" in BUG_HUNTER_ROLE.system_prompt.lower()
        assert "run_tests" in BUG_HUNTER_ROLE.tools
        assert BUG_HUNTER_ROLE.max_turns == 20

    def test_tester_role(self):
        assert TESTER_ROLE.name == "tester"
        assert "QA" in TESTER_ROLE.system_prompt
        assert "run_tests" in TESTER_ROLE.tools
        assert TESTER_ROLE.max_turns == 20

    def test_architect_role(self):
        assert ARCHITECT_ROLE.name == "architect"
        assert "architect" in ARCHITECT_ROLE.system_prompt.lower()
        assert "list_directory" in ARCHITECT_ROLE.tools
        assert ARCHITECT_ROLE.max_turns == 15

    def test_standard_roles_dict(self):
        assert "developer" in STANDARD_ROLES
        assert "code_reviewer" in STANDARD_ROLES
        assert "bug_hunter" in STANDARD_ROLES
        assert "tester" in STANDARD_ROLES
        assert "architect" in STANDARD_ROLES
        assert len(STANDARD_ROLES) == 5
        for name, role in STANDARD_ROLES.items():
            assert role.name == name


class TestRoleManager:
    """Test RoleManager class."""

    def test_create_manager(self):
        mgr = RoleManager()
        assert mgr is not None

    def test_get_existing_role(self):
        mgr = RoleManager()
        role = mgr.get_role("developer")
        assert role is not None
        assert role.name == "developer"

    def test_get_unknown_role(self):
        mgr = RoleManager()
        assert mgr.get_role("nonexistent") is None

    def test_list_roles(self):
        mgr = RoleManager()
        names = mgr.list_roles()
        assert len(names) == 5
        assert "developer" in names
        assert "code_reviewer" in names

    def test_register_custom_role(self):
        mgr = RoleManager()
        custom = HGJRole(
            name="security",
            description="Security analyst",
            system_prompt="Find security issues",
        )
        mgr.register_role(custom)
        role = mgr.get_role("security")
        assert role is not None
        assert role.description == "Security analyst"
        assert "security" in mgr.list_roles()

    def test_register_role_overwrites(self):
        mgr = RoleManager()
        old = mgr.get_role("developer")
        custom = HGJRole(
            name="developer",
            description="Custom developer",
            system_prompt="Custom prompt",
        )
        mgr.register_role(custom)
        role = mgr.get_role("developer")
        assert role is not None
        assert role.description == "Custom developer"

    def test_to_system_prompt(self):
        mgr = RoleManager()
        prompt = mgr.to_system_prompt("developer")
        assert "software" in prompt.lower()

    def test_to_system_prompt_unknown_role(self):
        mgr = RoleManager()
        with pytest.raises(ValueError, match="Unknown role"):
            mgr.to_system_prompt("nonexistent")

    def test_manager_has_standard_roles(self):
        mgr = RoleManager()
        for name in ["developer", "code_reviewer", "bug_hunter", "tester", "architect"]:
            role = mgr.get_role(name)
            assert role is not None, f"Missing role: {name}"
