"""SASHELP sample dataset schema definitions for context injection."""

SASHELP_CARS = """
SASHELP.CARS - Vehicle data (428 observations, 15 variables)
Columns:
- Make (char): Manufacturer name (e.g., Acura, BMW, Ford)
- Model (char): Model name
- Type (char): Vehicle type (Hybrid, SUV, Sedan, Sports, Truck, Wagon)
- Origin (char): Country of origin (Asia, Europe, USA)
- DriveTrain (char): Drive configuration (All, Front, Rear)
- MSRP (num): Manufacturer's suggested retail price in USD
- Invoice (num): Invoice price in USD
- EngineSize (num): Engine size in litres
- Cylinders (num): Number of cylinders
- Horsepower (num): Engine horsepower
- MPG_City (num): City miles per gallon
- MPG_Highway (num): Highway miles per gallon
- Weight (num): Vehicle weight in pounds
- Wheelbase (num): Wheelbase in inches
- Length (num): Vehicle length in inches
"""

SASHELP_CLASS = """
SASHELP.CLASS - Student measurements (19 observations, 5 variables)
Columns:
- Name (char): Student name
- Sex (char): Gender (M, F)
- Age (num): Age in years (11-16)
- Height (num): Height in inches
- Weight (num): Weight in pounds
"""

SASHELP_HEART = """
SASHELP.HEART - Framingham Heart Study (5209 observations, 17 variables)
Columns:
- Status (char): Vital status (Alive, Dead)
- DeathCause (char): Cause of death if applicable
- AgeCHDdiag (num): Age at CHD diagnosis
- Sex (char): Gender
- AgeAtStart (num): Age at study start
- Height (num): Height in inches
- Weight (num): Weight in pounds
- Diastolic (num): Diastolic blood pressure
- Systolic (num): Systolic blood pressure
- MRW (num): Metropolitan relative weight
- Smoking (char): Smoking status
- AgeAtDeath (num): Age at death if applicable
- Cholesterol (num): Cholesterol level
- Chol_Status (char): Cholesterol status category
- BP_Status (char): Blood pressure status
- Weight_Status (char): Weight status category
- Smoking_Status (char): Smoking status category
"""

ALL_SCHEMAS = f"""
Available SASHELP Datasets:

{SASHELP_CARS}

{SASHELP_CLASS}

{SASHELP_HEART}
"""
