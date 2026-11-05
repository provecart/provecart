import os
use_mcp = "{{ cookiecutter.use_mcp }}".lower() == "true"
if not use_mcp:
    p = os.path.join(os.getcwd(), "mcp_agent.py")
    if os.path.exists(p):
        os.remove(p)
print("Generated {{ cookiecutter.agent_name }} ({{ cookiecutter.project_slug }}) — run: python shopping_agent.py")
