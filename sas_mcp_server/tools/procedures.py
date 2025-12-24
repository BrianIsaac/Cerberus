"""MCP tools for SAS procedure operations."""

import re
from typing import Any

from fastmcp import FastMCP

PROCEDURE_DOCS: dict[str, dict[str, Any]] = {
    "PROC SQL": {
        "description": "Implements SQL queries within SAS",
        "syntax": "PROC SQL; SELECT columns FROM table WHERE condition; QUIT;",
        "common_clauses": ["SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "JOIN"],
        "examples": [
            "PROC SQL; SELECT Make, Model, MSRP FROM SASHELP.CARS WHERE MSRP > 30000; QUIT;",
            "PROC SQL; SELECT Type, AVG(MSRP) AS AvgPrice FROM SASHELP.CARS GROUP BY Type; QUIT;",
        ],
        "tips": [
            "Use QUIT; to end PROC SQL (not RUN;)",
            "Use CALCULATED to reference computed columns",
            "DISTINCT removes duplicate rows",
        ],
    },
    "DATA STEP": {
        "description": "Creates and manipulates SAS datasets",
        "syntax": "DATA output_dataset; SET input_dataset; /* transformations */; RUN;",
        "common_statements": ["SET", "IF-THEN", "DO-END", "RETAIN", "ARRAY", "KEEP", "DROP"],
        "examples": [
            "DATA expensive_cars; SET SASHELP.CARS; WHERE MSRP > 50000; RUN;",
            "DATA cars_with_value; SET SASHELP.CARS; Value = MSRP - Invoice; RUN;",
        ],
        "tips": [
            "Use RUN; to end DATA step",
            "Use WHERE to filter before processing",
            "Use IF to filter during processing",
        ],
    },
    "PROC MEANS": {
        "description": "Calculates descriptive statistics",
        "syntax": "PROC MEANS DATA=dataset; VAR numeric_vars; CLASS grouping_vars; RUN;",
        "statistics": ["N", "MEAN", "STD", "MIN", "MAX", "SUM", "MEDIAN", "Q1", "Q3"],
        "examples": [
            "PROC MEANS DATA=SASHELP.CARS; VAR MSRP Horsepower; RUN;",
            "PROC MEANS DATA=SASHELP.CARS MEAN MEDIAN; VAR MSRP; CLASS Type; RUN;",
        ],
        "tips": [
            "Use CLASS for grouping (no prior sorting needed)",
            "Specify statistics after MEANS keyword",
            "Use OUTPUT OUT= to save results",
        ],
    },
    "PROC FREQ": {
        "description": "Produces frequency and crosstabulation tables",
        "syntax": "PROC FREQ DATA=dataset; TABLES var1 * var2 / options; RUN;",
        "options": ["CHISQ", "NOCUM", "NOPERCENT", "NOROW", "NOCOL", "MISSING"],
        "examples": [
            "PROC FREQ DATA=SASHELP.CARS; TABLES Type; RUN;",
            "PROC FREQ DATA=SASHELP.CARS; TABLES Origin * Type / CHISQ; RUN;",
        ],
        "tips": [
            "Use * for crosstabulations",
            "Add / CHISQ for chi-square test",
            "Use WEIGHT for weighted frequencies",
        ],
    },
    "PROC SORT": {
        "description": "Sorts observations in a SAS dataset",
        "syntax": "PROC SORT DATA=dataset OUT=sorted_dataset; BY var1 var2; RUN;",
        "options": ["NODUPKEY", "NODUPRECS", "DESCENDING"],
        "examples": [
            "PROC SORT DATA=SASHELP.CARS; BY Make Model; RUN;",
            "PROC SORT DATA=SASHELP.CARS OUT=cars_sorted; BY DESCENDING MSRP; RUN;",
        ],
        "tips": [
            "Use OUT= to preserve original dataset",
            "DESCENDING applies only to following variable",
            "NODUPKEY removes duplicate key combinations",
        ],
    },
    "PROC PRINT": {
        "description": "Prints observations from a SAS dataset",
        "syntax": "PROC PRINT DATA=dataset; VAR variables; RUN;",
        "options": ["NOOBS", "LABEL", "N"],
        "examples": [
            "PROC PRINT DATA=SASHELP.CARS (OBS=10); VAR Make Model MSRP; RUN;",
            "PROC PRINT DATA=SASHELP.CLASS NOOBS; RUN;",
        ],
        "tips": [
            "Use (OBS=n) to limit output",
            "VAR statement specifies which columns",
            "WHERE statement filters rows",
        ],
    },
    "PROC CORR": {
        "description": "Computes correlation coefficients",
        "syntax": "PROC CORR DATA=dataset; VAR numeric_vars; WITH other_vars; RUN;",
        "options": ["PEARSON", "SPEARMAN", "KENDALL", "NOSIMPLE", "NOPROB"],
        "examples": [
            "PROC CORR DATA=SASHELP.CARS; VAR MSRP Horsepower Weight; RUN;",
            "PROC CORR DATA=SASHELP.CLASS; VAR Height Weight; RUN;",
        ],
        "tips": [
            "Use WITH for asymmetric correlation matrix",
            "SPEARMAN for non-parametric correlations",
            "Use PLOTS for scatter matrices",
        ],
    },
}


def register_procedure_tools(mcp: FastMCP) -> None:
    """Register procedure-related MCP tools.

    Args:
        mcp: FastMCP server instance.
    """

    @mcp.tool()
    async def get_procedure_docs(procedure_name: str) -> dict[str, Any]:
        """Get documentation for a SAS procedure.

        Args:
            procedure_name: Name of the procedure (e.g., PROC SQL, DATA STEP)

        Returns:
            Dictionary with procedure description, syntax, examples, and tips
        """
        proc_upper = procedure_name.upper()
        if proc_upper in ["SQL", "PROC SQL"]:
            proc_upper = "PROC SQL"
        elif proc_upper in ["DATA", "DATA STEP"]:
            proc_upper = "DATA STEP"
        elif proc_upper.startswith("PROC "):
            proc_upper = proc_upper
        else:
            proc_upper = f"PROC {proc_upper}"

        docs = PROCEDURE_DOCS.get(proc_upper)
        if not docs:
            return {
                "error": f"Documentation for '{procedure_name}' not found",
                "available_procedures": list(PROCEDURE_DOCS.keys()),
            }
        return {"procedure": proc_upper, **docs}

    @mcp.tool()
    async def validate_sas_syntax(code: str) -> dict[str, Any]:
        """Validate basic SAS syntax patterns.

        Performs lightweight syntax checking for common issues.
        Note: This is not a full SAS parser, just basic pattern validation.

        Args:
            code: SAS code to validate

        Returns:
            Dictionary with validation status and any issues found
        """
        issues = []

        lines = code.strip().split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.endswith(";") and not stripped.endswith("*/"):
                if not stripped.startswith("/*") and not stripped.startswith("*"):
                    if not any(kw in stripped.upper() for kw in ["DO", "THEN", "ELSE"]):
                        issues.append({
                            "line": i,
                            "issue": "Possible missing semicolon",
                            "code": stripped[:50],
                        })

        if "PROC SQL" in code.upper() and "QUIT;" not in code.upper():
            issues.append({
                "line": None,
                "issue": "PROC SQL should end with QUIT; not RUN;",
                "code": "PROC SQL ... QUIT;",
            })

        single_quotes = code.count("'") % 2
        double_quotes = code.count('"') % 2
        if single_quotes != 0:
            issues.append({
                "line": None,
                "issue": "Unbalanced single quotes",
                "code": None,
            })
        if double_quotes != 0:
            issues.append({
                "line": None,
                "issue": "Unbalanced double quotes",
                "code": None,
            })

        typo_patterns = [
            (r"\bFROM\s+FORM\b", "Possible typo: FORM should be FROM"),
            (r"\bSELCT\b", "Possible typo: SELCT should be SELECT"),
            (r"\bWHRER\b", "Possible typo: WHERER should be WHERE"),
        ]
        for pattern, message in typo_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({"line": None, "issue": message, "code": None})

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "issue_count": len(issues),
        }

    @mcp.tool()
    async def list_procedures() -> dict[str, Any]:
        """List all documented SAS procedures.

        Returns:
            Dictionary with list of procedures and their descriptions
        """
        procedures = []
        for name, docs in PROCEDURE_DOCS.items():
            procedures.append({
                "name": name,
                "description": docs["description"],
            })
        return {"procedures": procedures}
