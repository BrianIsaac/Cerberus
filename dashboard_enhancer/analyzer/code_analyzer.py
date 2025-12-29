"""Source code analysis for understanding agent purpose and domain."""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger()


@dataclass
class AgentProfile:
    """Profile of an agent's purpose and capabilities."""

    service_name: str
    agent_type: str
    domain: str
    description: str
    primary_actions: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    llm_provider: str = "unknown"
    framework: str = "unknown"
    files_analyzed: list[str] = field(default_factory=list)


class CodeAnalyzer:
    """Analyses agent source code to extract domain information."""

    LLM_PATTERNS = {
        "google.genai": "Google Gemini",
        "google-genai": "Google Gemini",
        "vertexai": "Vertex AI",
        "openai": "OpenAI",
        "anthropic": "Anthropic Claude",
        "langchain": "LangChain",
    }

    FRAMEWORK_PATTERNS = {
        "langgraph": "LangGraph",
        "langchain": "LangChain",
        "autogen": "AutoGen",
        "crewai": "CrewAI",
        "fastapi": "FastAPI",
    }

    TOOL_PATTERNS = {
        "mcp": "Model Context Protocol",
        "httpx": "HTTP Client",
        "datadog": "Datadog API",
    }

    def __init__(self, agent_dir: Path | str):
        """Initialise analyser with agent directory.

        Args:
            agent_dir: Path to agent source directory.

        Raises:
            ValueError: If agent directory does not exist.
        """
        self.agent_dir = Path(agent_dir)
        if not self.agent_dir.exists():
            raise ValueError(f"Agent directory not found: {agent_dir}")

    def analyze(self) -> AgentProfile:
        """Analyse agent source code and return profile.

        Returns:
            AgentProfile with extracted information.
        """
        logger.info("analyzing_agent", directory=str(self.agent_dir))

        files_to_analyze = self._find_key_files()

        imports: set[str] = set()
        functions: list[dict] = []
        docstrings: list[str] = []
        prompts: list[str] = []

        for file_path in files_to_analyze:
            file_info = self._analyze_file(file_path)
            imports.update(file_info.get("imports", []))
            functions.extend(file_info.get("functions", []))
            docstrings.extend(file_info.get("docstrings", []))
            prompts.extend(file_info.get("prompts", []))

        llm_provider = self._detect_llm_provider(imports)
        framework = self._detect_framework(imports)
        tools = self._detect_tools(imports)
        domain, description = self._extract_domain(docstrings, prompts, functions)
        agent_type = self._detect_agent_type()
        service_name = self._detect_service_name()
        primary_actions = self._extract_actions(functions)
        output_types = self._extract_output_types(functions)

        profile = AgentProfile(
            service_name=service_name,
            agent_type=agent_type,
            domain=domain,
            description=description,
            primary_actions=primary_actions,
            output_types=output_types,
            tools_used=tools,
            llm_provider=llm_provider,
            framework=framework,
            files_analyzed=[str(f) for f in files_to_analyze],
        )

        logger.info(
            "analysis_complete",
            service=profile.service_name,
            domain=profile.domain,
            llm_provider=profile.llm_provider,
        )

        return profile

    def _find_key_files(self) -> list[Path]:
        """Find key Python files to analyse."""
        key_patterns = [
            "main.py",
            "app.py",
            "workflow.py",
            "agent/*.py",
            "prompts.py",
            "prompts/*.py",
            "config.py",
        ]

        files = []
        for pattern in key_patterns:
            files.extend(self.agent_dir.glob(pattern))

        files = [
            f
            for f in files
            if "__pycache__" not in str(f) and not f.name.startswith("test_")
        ]

        return files[:10]

    def _analyze_file(self, file_path: Path) -> dict:
        """Parse a Python file and extract information.

        Args:
            file_path: Path to the Python file.

        Returns:
            Dictionary with imports, functions, docstrings, and prompts.
        """
        try:
            with open(file_path) as f:
                content = f.read()
                tree = ast.parse(content)
        except SyntaxError:
            logger.warning("syntax_error", file=str(file_path))
            return {}

        imports: list[str] = []
        functions: list[dict] = []
        docstrings: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = {
                    "name": node.name,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "args": [arg.arg for arg in node.args.args],
                }

                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                ):
                    docstring = node.body[0].value.value
                    func_info["docstring"] = docstring
                    docstrings.append(docstring)

                functions.append(func_info)

        prompt_pattern = r'"""[\s\S]*?"""'
        prompts = re.findall(prompt_pattern, content)

        return {
            "imports": imports,
            "functions": functions,
            "docstrings": docstrings,
            "prompts": prompts,
        }

    def _detect_llm_provider(self, imports: set[str]) -> str:
        """Detect LLM provider from imports.

        Args:
            imports: Set of import names.

        Returns:
            Detected LLM provider name.
        """
        for imp in imports:
            imp_lower = imp.lower()
            for pattern, provider in self.LLM_PATTERNS.items():
                if pattern in imp_lower:
                    return provider
        return "unknown"

    def _detect_framework(self, imports: set[str]) -> str:
        """Detect agent framework from imports.

        Args:
            imports: Set of import names.

        Returns:
            Detected framework name.
        """
        for imp in imports:
            imp_lower = imp.lower()
            for pattern, framework in self.FRAMEWORK_PATTERNS.items():
                if pattern in imp_lower:
                    return framework
        return "custom"

    def _detect_tools(self, imports: set[str]) -> list[str]:
        """Detect tools used from imports.

        Args:
            imports: Set of import names.

        Returns:
            List of detected tool names.
        """
        tools = []
        for imp in imports:
            imp_lower = imp.lower()
            for pattern, tool in self.TOOL_PATTERNS.items():
                if pattern in imp_lower and tool not in tools:
                    tools.append(tool)
        return tools

    def _extract_domain(
        self,
        docstrings: list[str],
        prompts: list[str],
        functions: list[dict],
    ) -> tuple[str, str]:
        """Extract domain and description from content.

        Args:
            docstrings: List of docstrings found.
            prompts: List of prompt strings found.
            functions: List of function info dicts.

        Returns:
            Tuple of (domain, description).
        """
        all_text = " ".join(docstrings + prompts)
        all_text_lower = all_text.lower()

        domain_keywords = {
            "sas": "SAS statistical programming",
            "triage": "incident triage",
            "incident": "incident management",
            "code generation": "code generation",
            "analysis": "data analysis",
            "research": "research and exploration",
            "assistant": "general assistance",
        }

        for keyword, domain in domain_keywords.items():
            if keyword in all_text_lower:
                description = next(
                    (d.strip()[:200] for d in docstrings if len(d.strip()) > 20),
                    f"AI agent for {domain}",
                )
                return domain, description

        dir_name = self.agent_dir.name.replace("_", " ").replace("-", " ")
        return dir_name, f"AI agent: {dir_name}"

    def _detect_agent_type(self) -> str:
        """Detect agent type from config or directory.

        Returns:
            Detected agent type.
        """
        config_path = self.agent_dir / "config.py"
        if config_path.exists():
            with open(config_path) as f:
                content = f.read()
                match = re.search(
                    r'agent_type["\']?\s*[:=]\s*["\'](\w+)', content, re.I
                )
                if match:
                    return match.group(1)

        dir_name = self.agent_dir.name.lower()
        if "triage" in dir_name:
            return "triage"
        elif "generator" in dir_name or "gen" in dir_name:
            return "code-generation"
        elif "research" in dir_name:
            return "research"
        elif "assist" in dir_name:
            return "assistant"
        else:
            return "analysis"

    def _detect_service_name(self) -> str:
        """Detect service name from config.

        Returns:
            Detected service name.
        """
        config_path = self.agent_dir / "config.py"
        if config_path.exists():
            with open(config_path) as f:
                content = f.read()
                match = re.search(
                    r'dd_service["\']?\s*[:=]\s*["\']([^"\']+)', content, re.I
                )
                if match:
                    return match.group(1)

        return self.agent_dir.name.replace("_", "-")

    def _extract_actions(self, functions: list[dict]) -> list[str]:
        """Extract primary actions from function names.

        Args:
            functions: List of function info dicts.

        Returns:
            List of action function names.
        """
        action_verbs = [
            "generate",
            "create",
            "analyze",
            "triage",
            "process",
            "handle",
            "run",
        ]
        actions = []

        for func in functions:
            name = func["name"].lower()
            for verb in action_verbs:
                if verb in name and func["name"] not in [
                    "__init__",
                    "__aenter__",
                    "__aexit__",
                ]:
                    actions.append(func["name"])
                    break

        return actions[:5]

    def _extract_output_types(self, functions: list[dict]) -> list[str]:
        """Extract output types from function docstrings.

        Args:
            functions: List of function info dicts.

        Returns:
            List of output type keywords.
        """
        output_keywords = [
            "code",
            "hypothesis",
            "report",
            "response",
            "result",
            "analysis",
        ]
        outputs: set[str] = set()

        for func in functions:
            docstring = func.get("docstring", "").lower()
            for keyword in output_keywords:
                if keyword in docstring:
                    outputs.add(keyword)

        return list(outputs)
