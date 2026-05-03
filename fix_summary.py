"""Fix the PM summary block to use simple LLM call instead of full Agent."""
import re

path = r"C:\Users\biong\Desktop\HarnessGenJ-dev\src\harnessgenj_dev\web\dashboard.py"
with open(path, encoding="utf-8") as f:
    c = f.read()

start = c.find("# PM synthesizes final summary")
end = c.find("async def run_develop_oneshot", start)

if start < 0 or end < 0:
    print("Could not find summary block boundaries")
    exit(1)

new_block = """        # PM ALWAYS synthesizes final summary (mandatory step)
        await self.send({"type": "agent_dispatch", "role": "product_manager", "role_display": "产品经理", "status": "started"})
        try:
            from ..llm.gateway import LLMGateway
            gw = LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None)
            rlines = []
            for r in agent_results:
                rlines.append("### " + self._ROLE_DISPLAY.get(r, r) + "\\n" + agent_results[r][:1500])
            prompt_str = (
                "You are the PM. Your team completed work.\\n"
                "Write a project update for the user.\\n\\n"
                "## User Request\\n" + user_request[:1000] + "\\n\\n"
                + "\\n".join(rlines) + "\\n\\n"
                "Summarize what was accomplished, key outcomes, and next steps."
            )
            resp = await gw.chat(messages=[{"role": "user", "content": prompt_str}], model=_get_model())
            return resp.content or "Team work complete."
        except Exception:
            fb = "## 团队工作完成\\n\\n"
            for r in agent_results:
                fb += "- **" + self._ROLE_DISPLAY.get(r, r) + "**: 已完成\\n"
            return fb
"""

c = c[:start] + new_block + c[end:]

with open(path, "w", encoding="utf-8") as f:
    f.write(c)

import ast
try:
    ast.parse(c)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Error at line {e.lineno}: {e.msg}")
