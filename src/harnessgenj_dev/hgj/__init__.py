"""HGJ Framework Integration.

This module bridges HGJ-dev (standalone AI development tool) with the
original HGJ framework (AI Agent coordination framework).

HGJ provides role-based workflows (Developer, CodeReviewer, BugHunter,
Tester, etc.) that are orchestrated through a ReAct loop. This module
adapts HGJ's coordination patterns to work with HGJ-dev's LLM Gateway,
Tool Set, and Agent Core.

Architecture:
    HGJ Roles    -> System Prompts (core/system_prompt.py)
    HGJ Workflows -> Agent ReAct Loop (core/agent.py)
    HGJ GAN Loop  -> Adversarial testing (hgj/integration.py)
"""

from .integration import HGJDevResult, HGJIntegration
from .roles import RoleManager
from .workflows import WorkflowOrchestrator

__all__ = ["WorkflowOrchestrator", "RoleManager", "HGJIntegration", "HGJDevResult"]
