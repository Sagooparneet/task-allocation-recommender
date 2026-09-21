# task-allocation-recommender
Explainable Knowledge Graph-Driven Hybrid Recommender for Intelligent Task Allocation in Distributed Onboarding Operations

## How to Run the Application

### 1. Clone the repository

```bash
git clone https://github.com/Sagooparneet/task-allocation-recommender.git
```

Move into the project folder:

```bash
cd task-allocation-recommender
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

For Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the virtual environment again:

```powershell
venv\Scripts\Activate.ps1
```

### 4. Install the required packages

```bash
pip install -r requirements.txt
```

### 5. Create and seed the database

```bash
python seed.py
```

This creates the SQLite database and adds mock data for testing.

### 6. Run the application

```bash
python run.py
```

### 7. Open the application

Open:

```text
http://127.0.0.1:5000
```

## Test Login Accounts

### Supervisor

```text
Email: supervisor@example.com
Password: password123
```

### Onboarding Agent

```text
Email: grace@example.com
Password: password123
```

### Administrator

```text
Email: admin@example.com
Password: password123
```

These accounts are for development and testing only.