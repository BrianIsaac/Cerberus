"""SASHELP dataset definitions with sample data for MCP tools."""

from typing import Any

DATASET_SCHEMAS: dict[str, dict[str, Any]] = {
    "SASHELP.CARS": {
        "name": "SASHELP.CARS",
        "description": "Vehicle data with specifications and pricing",
        "observations": 428,
        "columns": [
            {"name": "Make", "type": "char", "length": 13, "description": "Manufacturer name"},
            {"name": "Model", "type": "char", "length": 40, "description": "Model name"},
            {"name": "Type", "type": "char", "length": 8, "description": "Vehicle type"},
            {"name": "Origin", "type": "char", "length": 6, "description": "Country of origin"},
            {"name": "DriveTrain", "type": "char", "length": 5, "description": "Drive configuration"},
            {"name": "MSRP", "type": "num", "format": "DOLLAR8.", "description": "Suggested retail price"},
            {"name": "Invoice", "type": "num", "format": "DOLLAR8.", "description": "Invoice price"},
            {"name": "EngineSize", "type": "num", "format": "3.1", "description": "Engine size in litres"},
            {"name": "Cylinders", "type": "num", "format": "2.", "description": "Number of cylinders"},
            {"name": "Horsepower", "type": "num", "format": "3.", "description": "Engine horsepower"},
            {"name": "MPG_City", "type": "num", "format": "2.", "description": "City miles per gallon"},
            {"name": "MPG_Highway", "type": "num", "format": "2.", "description": "Highway miles per gallon"},
            {"name": "Weight", "type": "num", "format": "5.", "description": "Vehicle weight in pounds"},
            {"name": "Wheelbase", "type": "num", "format": "3.", "description": "Wheelbase in inches"},
            {"name": "Length", "type": "num", "format": "3.", "description": "Vehicle length in inches"},
        ],
    },
    "SASHELP.CLASS": {
        "name": "SASHELP.CLASS",
        "description": "Student physical measurements",
        "observations": 19,
        "columns": [
            {"name": "Name", "type": "char", "length": 8, "description": "Student name"},
            {"name": "Sex", "type": "char", "length": 1, "description": "Gender (M/F)"},
            {"name": "Age", "type": "num", "format": "2.", "description": "Age in years"},
            {"name": "Height", "type": "num", "format": "5.1", "description": "Height in inches"},
            {"name": "Weight", "type": "num", "format": "5.1", "description": "Weight in pounds"},
        ],
    },
    "SASHELP.HEART": {
        "name": "SASHELP.HEART",
        "description": "Framingham Heart Study data",
        "observations": 5209,
        "columns": [
            {"name": "Status", "type": "char", "length": 5, "description": "Vital status"},
            {"name": "DeathCause", "type": "char", "length": 15, "description": "Cause of death"},
            {"name": "AgeCHDdiag", "type": "num", "format": "3.", "description": "Age at CHD diagnosis"},
            {"name": "Sex", "type": "char", "length": 6, "description": "Gender"},
            {"name": "AgeAtStart", "type": "num", "format": "2.", "description": "Age at study start"},
            {"name": "Height", "type": "num", "format": "5.2", "description": "Height in inches"},
            {"name": "Weight", "type": "num", "format": "6.2", "description": "Weight in pounds"},
            {"name": "Diastolic", "type": "num", "format": "3.", "description": "Diastolic blood pressure"},
            {"name": "Systolic", "type": "num", "format": "3.", "description": "Systolic blood pressure"},
            {"name": "MRW", "type": "num", "format": "6.2", "description": "Metropolitan relative weight"},
            {"name": "Smoking", "type": "char", "length": 22, "description": "Smoking status"},
            {"name": "AgeAtDeath", "type": "num", "format": "3.", "description": "Age at death"},
            {"name": "Cholesterol", "type": "num", "format": "3.", "description": "Cholesterol level"},
            {"name": "Chol_Status", "type": "char", "length": 11, "description": "Cholesterol status"},
            {"name": "BP_Status", "type": "char", "length": 7, "description": "Blood pressure status"},
            {"name": "Weight_Status", "type": "char", "length": 11, "description": "Weight status"},
            {"name": "Smoking_Status", "type": "char", "length": 10, "description": "Smoking status category"},
        ],
    },
}

SAMPLE_DATA: dict[str, list[dict[str, Any]]] = {
    "SASHELP.CARS": [
        {"Make": "Acura", "Model": "MDX", "Type": "SUV", "Origin": "Asia", "DriveTrain": "All", "MSRP": 36945, "Invoice": 33337, "EngineSize": 3.5, "Cylinders": 6, "Horsepower": 265, "MPG_City": 17, "MPG_Highway": 23, "Weight": 4451, "Wheelbase": 106, "Length": 189},
        {"Make": "Acura", "Model": "RSX Type S 2dr", "Type": "Sedan", "Origin": "Asia", "DriveTrain": "Front", "MSRP": 23820, "Invoice": 21761, "EngineSize": 2.0, "Cylinders": 4, "Horsepower": 200, "MPG_City": 24, "MPG_Highway": 31, "Weight": 2778, "Wheelbase": 101, "Length": 172},
        {"Make": "Acura", "Model": "TSX 4dr", "Type": "Sedan", "Origin": "Asia", "DriveTrain": "Front", "MSRP": 26990, "Invoice": 24647, "EngineSize": 2.4, "Cylinders": 4, "Horsepower": 200, "MPG_City": 22, "MPG_Highway": 29, "Weight": 3230, "Wheelbase": 105, "Length": 183},
        {"Make": "Acura", "Model": "TL 4dr", "Type": "Sedan", "Origin": "Asia", "DriveTrain": "Front", "MSRP": 33195, "Invoice": 30299, "EngineSize": 3.2, "Cylinders": 6, "Horsepower": 270, "MPG_City": 20, "MPG_Highway": 28, "Weight": 3575, "Wheelbase": 108, "Length": 186},
        {"Make": "Acura", "Model": "3.5 RL 4dr", "Type": "Sedan", "Origin": "Asia", "DriveTrain": "Front", "MSRP": 43755, "Invoice": 39014, "EngineSize": 3.5, "Cylinders": 6, "Horsepower": 225, "MPG_City": 18, "MPG_Highway": 24, "Weight": 3880, "Wheelbase": 115, "Length": 197},
    ],
    "SASHELP.CLASS": [
        {"Name": "Alfred", "Sex": "M", "Age": 14, "Height": 69.0, "Weight": 112.5},
        {"Name": "Alice", "Sex": "F", "Age": 13, "Height": 56.5, "Weight": 84.0},
        {"Name": "Barbara", "Sex": "F", "Age": 13, "Height": 65.3, "Weight": 98.0},
        {"Name": "Carol", "Sex": "F", "Age": 14, "Height": 62.8, "Weight": 102.5},
        {"Name": "Henry", "Sex": "M", "Age": 14, "Height": 63.5, "Weight": 102.5},
    ],
    "SASHELP.HEART": [
        {"Status": "Alive", "DeathCause": None, "AgeCHDdiag": None, "Sex": "Female", "AgeAtStart": 42, "Height": 62.5, "Weight": 140.0, "Diastolic": 78, "Systolic": 130, "MRW": 115.45, "Smoking": "Non-smoker", "AgeAtDeath": None, "Cholesterol": 230, "Chol_Status": "High", "BP_Status": "Normal", "Weight_Status": "Overweight", "Smoking_Status": "Non-smoker"},
        {"Status": "Alive", "DeathCause": None, "AgeCHDdiag": None, "Sex": "Male", "AgeAtStart": 52, "Height": 70.0, "Weight": 185.0, "Diastolic": 88, "Systolic": 150, "MRW": 122.37, "Smoking": "Light (1-5)", "AgeAtDeath": None, "Cholesterol": 260, "Chol_Status": "High", "BP_Status": "High", "Weight_Status": "Overweight", "Smoking_Status": "Light"},
        {"Status": "Dead", "DeathCause": "Coronary Heart Disease", "AgeCHDdiag": 58, "Sex": "Male", "AgeAtStart": 48, "Height": 68.0, "Weight": 195.0, "Diastolic": 92, "Systolic": 165, "MRW": 130.26, "Smoking": "Heavy (16-25)", "AgeAtDeath": 62, "Cholesterol": 290, "Chol_Status": "High", "BP_Status": "High", "Weight_Status": "Overweight", "Smoking_Status": "Heavy"},
        {"Status": "Alive", "DeathCause": None, "AgeCHDdiag": None, "Sex": "Female", "AgeAtStart": 38, "Height": 64.0, "Weight": 125.0, "Diastolic": 72, "Systolic": 118, "MRW": 98.43, "Smoking": "Non-smoker", "AgeAtDeath": None, "Cholesterol": 195, "Chol_Status": "Desirable", "BP_Status": "Normal", "Weight_Status": "Normal", "Smoking_Status": "Non-smoker"},
        {"Status": "Alive", "DeathCause": None, "AgeCHDdiag": None, "Sex": "Male", "AgeAtStart": 45, "Height": 72.0, "Weight": 175.0, "Diastolic": 80, "Systolic": 135, "MRW": 105.82, "Smoking": "Moderate (6-15)", "AgeAtDeath": None, "Cholesterol": 225, "Chol_Status": "High", "BP_Status": "Normal", "Weight_Status": "Normal", "Smoking_Status": "Moderate"},
    ],
}


def get_schema(dataset_name: str) -> dict[str, Any] | None:
    """Get schema for a dataset.

    Args:
        dataset_name: Name of the SASHELP dataset.

    Returns:
        Dataset schema dictionary or None if not found.
    """
    return DATASET_SCHEMAS.get(dataset_name.upper())


def get_sample(dataset_name: str, n_rows: int = 5) -> list[dict[str, Any]]:
    """Get sample data for a dataset.

    Args:
        dataset_name: Name of the SASHELP dataset.
        n_rows: Number of rows to return.

    Returns:
        List of sample data rows.
    """
    data = SAMPLE_DATA.get(dataset_name.upper(), [])
    return data[:n_rows]


def list_datasets() -> list[str]:
    """List all available datasets.

    Returns:
        List of dataset names.
    """
    return list(DATASET_SCHEMAS.keys())
