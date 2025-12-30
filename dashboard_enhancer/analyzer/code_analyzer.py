"""Source code analysis for understanding agent purpose and domain."""

import ast
import base64
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
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
    llmobs_enabled: bool = False
    llmobs_decorators: list[str] = field(default_factory=list)
    span_operations: list[str] = field(default_factory=list)
    evaluation_context: dict = field(default_factory=dict)


class CodeAnalyzer:
    """Analyses agent source code to extract domain information.

    Supports both local directories and GitHub repository URLs.

    Examples:
        # Local directory
        analyzer = CodeAnalyzer("/path/to/agent")

        # GitHub URL (public repo)
        analyzer = CodeAnalyzer("https://github.com/owner/repo/tree/main/agent_dir")

        # GitHub URL with token (private repo)
        analyzer = CodeAnalyzer(
            "https://github.com/owner/repo/tree/main/agent_dir",
            github_token="ghp_xxx"
        )
    """

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

    LLMOBS_PATTERNS = {
        "LLMObs.enable": "llmobs_enabled",
        "@llm": "llm_decorator",
        "@workflow": "workflow_decorator",
        "@tool": "tool_decorator",
        "LLMObs.annotate": "annotate_calls",
    }

    SPAN_TYPE_PATTERNS = {
        "@llm": "llm",
        "@workflow": "workflow",
        "@tool": "tool",
        "@task": "task",
        "@agent": "agent",
    }

    GITHUB_API_BASE = "https://api.github.com"

    def __init__(self, agent_source: Path | str, github_token: str | None = None):
        """Initialise analyser with agent directory or GitHub URL.

        Args:
            agent_source: Local path or GitHub URL to agent source.
            github_token: Optional GitHub token for private repos.

        Raises:
            ValueError: If local directory does not exist or GitHub URL is invalid.
        """
        self.github_token = github_token
        self._temp_dir: tempfile.TemporaryDirectory | None = None

        source_str = str(agent_source)

        if self._is_github_url(source_str):
            self.agent_dir = self._fetch_from_github(source_str)
            self._is_github = True
        else:
            self.agent_dir = Path(agent_source)
            self._is_github = False
            if not self.agent_dir.exists():
                raise ValueError(f"Agent directory not found: {agent_source}")

    def __del__(self):
        """Clean up temporary directory if created."""
        if self._temp_dir:
            self._temp_dir.cleanup()

    def _is_github_url(self, source: str) -> bool:
        """Check if source is a GitHub URL.

        Args:
            source: Source string to check.

        Returns:
            True if source is a GitHub URL.
        """
        return source.startswith("https://github.com/") or source.startswith("github.com/")

    def _parse_github_url(self, url: str) -> tuple[str, str, str, str]:
        """Parse GitHub URL into components.

        Args:
            url: GitHub URL (e.g., https://github.com/owner/repo/tree/main/path)

        Returns:
            Tuple of (owner, repo, branch, path).

        Raises:
            ValueError: If URL format is invalid.
        """
        if url.startswith("github.com/"):
            url = "https://" + url

        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")

        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")

        owner = parts[0]
        repo = parts[1]

        # Default branch and path
        branch = "main"
        path = ""

        # Parse /tree/branch/path or /blob/branch/path
        if len(parts) > 3 and parts[2] in ("tree", "blob"):
            branch = parts[3]
            if len(parts) > 4:
                path = "/".join(parts[4:])
        elif len(parts) > 2:
            # Assume it's just owner/repo/path with default branch
            path = "/".join(parts[2:])

        return owner, repo, branch, path

    def _fetch_from_github(self, url: str) -> Path:
        """Fetch code from GitHub repository.

        Args:
            url: GitHub URL to fetch from.

        Returns:
            Path to temporary directory containing fetched files.

        Raises:
            ValueError: If fetching fails.
        """
        owner, repo, branch, path = self._parse_github_url(url)

        logger.info(
            "fetching_from_github",
            owner=owner,
            repo=repo,
            branch=branch,
            path=path,
        )

        # Create temp directory
        self._temp_dir = tempfile.TemporaryDirectory(prefix="agent_code_")
        temp_path = Path(self._temp_dir.name)

        # Fetch directory contents
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        try:
            self._fetch_directory(owner, repo, branch, path, temp_path, headers)
        except Exception as e:
            logger.error("github_fetch_failed", error=str(e))
            raise ValueError(f"Failed to fetch from GitHub: {e}")

        return temp_path

    def _fetch_directory(
        self,
        owner: str,
        repo: str,
        branch: str,
        path: str,
        local_dir: Path,
        headers: dict,
    ) -> None:
        """Recursively fetch directory contents from GitHub.

        Args:
            owner: Repository owner.
            repo: Repository name.
            branch: Branch name.
            path: Path within repository.
            local_dir: Local directory to save files to.
            headers: HTTP headers for requests.
        """
        api_url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        if branch != "main":
            api_url += f"?ref={branch}"

        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers)

            if response.status_code == 404:
                raise ValueError(f"Path not found: {path}")
            elif response.status_code == 403:
                raise ValueError("Rate limit exceeded or authentication required")
            elif response.status_code != 200:
                raise ValueError(f"GitHub API error: {response.status_code}")

            contents = response.json()

            # Handle single file response
            if isinstance(contents, dict):
                contents = [contents]

            for item in contents:
                item_path = local_dir / item["name"]

                if item["type"] == "file" and item["name"].endswith(".py"):
                    # Fetch file content
                    if item.get("content"):
                        content = base64.b64decode(item["content"]).decode("utf-8")
                    else:
                        # Fetch from download_url for larger files
                        file_response = client.get(item["download_url"], headers=headers)
                        content = file_response.text

                    item_path.write_text(content)
                    logger.debug("fetched_file", path=str(item_path))

                elif item["type"] == "dir":
                    # Recursively fetch subdirectories (limit depth)
                    if item["name"] not in ("__pycache__", ".git", "tests", "test"):
                        item_path.mkdir(exist_ok=True)
                        sub_path = f"{path}/{item['name']}" if path else item["name"]
                        self._fetch_directory(
                            owner, repo, branch, sub_path, item_path, headers
                        )

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
        all_content: str = ""
        llmobs_info = {"enabled": False, "decorators": [], "has_annotate": False}

        for file_path in files_to_analyze:
            with open(file_path) as f:
                content = f.read()
                all_content += content + "\n"

            file_info = self._analyze_file(file_path)
            imports.update(file_info.get("imports", []))
            functions.extend(file_info.get("functions", []))
            docstrings.extend(file_info.get("docstrings", []))
            prompts.extend(file_info.get("prompts", []))

            file_llmobs = self._detect_llmobs_usage(content, imports)
            if file_llmobs["enabled"]:
                llmobs_info["enabled"] = True
            llmobs_info["decorators"].extend(file_llmobs["decorators"])
            if file_llmobs["has_annotate"]:
                llmobs_info["has_annotate"] = True

        llm_provider = self._detect_llm_provider(imports)
        framework = self._detect_framework(imports)
        tools = self._detect_tools(imports)
        domain, description = self._extract_domain(docstrings, prompts, functions)
        agent_type = self._detect_agent_type()
        service_name = self._detect_service_name()
        primary_actions = self._extract_actions(functions)
        output_types = self._extract_output_types(functions)

        span_operations = self._extract_span_operations(functions, all_content)
        evaluation_context = self._extract_evaluation_context(
            docstrings, functions, output_types
        )

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
            llmobs_enabled=llmobs_info["enabled"],
            llmobs_decorators=list(set(llmobs_info["decorators"])),
            span_operations=span_operations,
            evaluation_context=evaluation_context,
        )

        logger.info(
            "analysis_complete",
            service=profile.service_name,
            domain=profile.domain,
            llmobs_enabled=profile.llmobs_enabled,
            span_operations_count=len(profile.span_operations),
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
            "observability.py",
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
                    if isinstance(docstring, str):
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

    def _detect_llmobs_usage(self, content: str, imports: set[str]) -> dict:
        """Detect LLM Observability usage patterns.

        Args:
            content: File content.
            imports: Set of imports.

        Returns:
            Dict with LLMObs usage details.
        """
        result = {
            "enabled": False,
            "decorators": [],
            "has_annotate": False,
        }

        if "ddtrace" in imports or "LLMObs" in content:
            result["enabled"] = "LLMObs.enable" in content

        for pattern, decorator_type in self.LLMOBS_PATTERNS.items():
            if pattern in content:
                if decorator_type.endswith("_decorator"):
                    result["decorators"].append(decorator_type.replace("_decorator", ""))
                elif decorator_type == "annotate_calls":
                    result["has_annotate"] = True

        return result

    def _extract_span_operations(self, functions: list[dict], content: str) -> list[str]:
        """Extract span operation names from decorated functions.

        Args:
            functions: List of function info dicts.
            content: Full file content.

        Returns:
            List of span operation names.
        """
        operations = []

        for func in functions:
            func_name = func["name"]
            for pattern, span_type in self.SPAN_TYPE_PATTERNS.items():
                # Match both @decorator and @decorator(...) forms
                pattern_regex = rf'{pattern}(?:\([^)]*\))?\s*\n\s*(async\s+)?def\s+{func_name}'
                if re.search(pattern_regex, content):
                    operations.append(f"{span_type}:{func_name}")
                    break

        return operations

    def _extract_evaluation_context(
        self,
        docstrings: list[str],
        functions: list[dict],
        output_types: list[str],
    ) -> dict:
        """Extract context useful for generating evaluations.

        Args:
            docstrings: List of docstrings.
            functions: List of function info.
            output_types: Detected output types.

        Returns:
            Context dict for evaluation generation.
        """
        context = {
            "output_format": "unknown",
            "validation_hints": [],
            "quality_aspects": [],
        }

        all_text = " ".join(docstrings).lower()

        if "code" in output_types or "sas" in all_text:
            context["output_format"] = "code"
            context["quality_aspects"] = ["syntax_validity", "correctness", "efficiency"]
        elif "json" in all_text or "structured" in all_text:
            context["output_format"] = "structured"
            context["quality_aspects"] = ["schema_compliance", "completeness"]
        elif "response" in output_types or "answer" in all_text:
            context["output_format"] = "text"
            context["quality_aspects"] = ["relevancy", "helpfulness", "accuracy"]

        validation_keywords = ["must", "should", "validate", "check", "ensure", "verify"]
        for doc in docstrings:
            for keyword in validation_keywords:
                if keyword in doc.lower():
                    sentences = doc.split(".")
                    for sentence in sentences:
                        if keyword in sentence.lower():
                            context["validation_hints"].append(sentence.strip())
                            break

        return context
