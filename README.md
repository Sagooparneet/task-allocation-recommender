# Intelligent Task Allocation System

## Explainable Knowledge Graph-Driven Hybrid Recommender for Intelligent Task Allocation in Distributed Onboarding Operations

This project develops an intelligent task allocation system for distributed onboarding operations. The system recommends suitable onboarding agents for tasks using a hybrid recommendation approach that combines Content-Based Filtering, Collaborative Filtering and Knowledge Graph reasoning.

The application also provides explanations for recommendations so that supervisors can understand why an agent was recommended before making the final assignment decision.

---

## Main System Roles

The system contains three user roles:

- Supervisor — creates tasks, views recommendations and assigns agents.
- Onboarding Agent — views assigned tasks and marks completed tasks.
- Administrator — accesses the administrator area of the system.

---

## Current Core Workflow

The implemented workflow is:

```text
Supervisor Login
      ↓
Create Task
      ↓
Select Required Skills
      ↓
Generate Agent Recommendations
      ↓
Hybrid Recommender
(CBF + CF + Knowledge Graph)
      ↓
Rank Available Agents
      ↓
Generate Explanations
      ↓
Supervisor Reviews Recommendation
      ↓
Assign Agent
      ↓
Agent Views Assigned Task
      ↓
Agent Completes Task
      ↓
Supervisor Sees Completed Status
```

---

## Recommendation Architecture

The recommendation system combines three recommendation components.

### Content-Based Filtering

Content-Based Filtering compares the requirements of a task with agent profile information.

The Flask application currently considers:

```text
Skill Match        = 50%
Specialization     = 20%
Location           = 10%
Performance        = 10%
Workload           = 10%
```

The live Flask implementation uses the information currently available in the application database.

---

### Collaborative Filtering

Collaborative Filtering uses historical completed task information to identify patterns between agents and task types.

The research experiment uses historical interaction information.

The live Flask application uses completed task-type history available in the application database. Where there is insufficient historical information, a neutral score of `0.50` is used instead of inventing historical evidence.

---

### Knowledge Graph

The Knowledge Graph represents relationships between entities such as:

```text
Agents
Tasks
Skills
Locations
Completed Tasks
```

The Flask implementation uses these relationships to calculate a Knowledge Graph suitability score.

The Knowledge Graph component considers:

```text
Skill relationships          = 50%
Location relationship        = 15%
Historical task type         = 20%
Historical performance       = 15%
```

---

## Hybrid Recommendation

The final hybrid recommendation score combines the three model components using fixed weights:

```text
Hybrid Score =
(0.30 × Content-Based Score)
+
(0.30 × Collaborative Filtering Score)
+
(0.40 × Knowledge Graph Score)
```

The weights are:

| Component | Weight |
|---|---:|
| Content-Based Filtering | 30% |
| Collaborative Filtering | 30% |
| Knowledge Graph | 40% |

These weights were selected using the validation dataset and were fixed before final testing.

The final test dataset was not used to retune the model.

---

## Recommendation Suitability Threshold

The application uses a suitability threshold of:

```text
60%
```

A recommendation scoring at least 60% is labelled:

```text
Suitable
```

A recommendation below 60% is labelled:

```text
Supervisor review
```

The system is designed as a decision-support system rather than a fully automatic assignment system.

Therefore, a supervisor may still manually assign an agent below the threshold using the `Assign Anyway` option after reviewing the recommendation explanation.

---

## Explainability

Each recommendation provides an overall match score and human-readable reasons that may include:

```text
Required skill match
Specialization match
Location match
Manageable workload
Performance information
Historical recommendation evidence
Previous experience with similar task types
```

Detailed component scores can also be viewed by the supervisor for additional transparency.

---

# Data Preparation

The current development dataset contains synthetic onboarding-related data created for development and experimental testing.

The synthetic data includes:

```text
100 onboarding agents
8 onboarding-related skills
2,000 tasks
1,304 completed historical interactions
```

Example skills include:

```text
KYC Verification
SIM Registration
M-PESA Onboarding
Account Activation
Customer Service
Identity Document Verification
Digital Registration
Mobile Financial Services
```

Synthetic data is used to develop and verify the recommendation pipeline while waiting for industry data.

It must not be interpreted as final evidence of performance in a real operational environment.

---

## Dataset Split

Historical interactions were separated into:

| Dataset | Percentage | Approximate Records |
|---|---:|---:|
| Training | 70% | 912 |
| Validation | 15% | 196 |
| Test | 15% | 196 |

The training dataset is used to develop the recommendation components.

The validation dataset is used for development decisions and hybrid weight selection.

The test dataset is reserved for final evaluation and is not used for tuning the model.

A fixed random seed of:

```text
42
```

is used during data preparation for reproducibility.

---

# Machine Learning and Recommendation Experiments

The main notebook sequence is:

```text
notebooks/
│
├── 01_data_preparation.ipynb
├── 02_content_based_baseline.ipynb
├── 03_collaborative_filtering.ipynb
├── 04_knowledge_graph.ipynb
├── 05_hybrid_recommender.ipynb
└── 06_model_evaluation.ipynb
```

The notebooks should be executed in this order.

---

## Experiment Runs

The current experiment identifiers are:

```text
CBF_RUN_001
CF_RUN_001
KG_RUN_001
HYBRID_RUN_001
FINAL_EVAL_001
```

Experiment outputs are stored under:

```text
experiments/
```

The experiment evidence includes items such as model configurations, evaluation metrics, predictions and plots.

---

# Evaluation

The models are evaluated using recommendation ranking metrics such as:

```text
Hit Rate@K
MAP@K
```

The final unseen test results at Top-5 were:

| Model | Hit Rate@5 | MAP@5 |
|---|---:|---:|
| Content-Based Filtering | 0.214286 | 0.134354 |
| Collaborative Filtering | 0.076531 | 0.043707 |
| Knowledge Graph | 0.341837 | 0.172534 |
| Hybrid Recommender | 0.306122 | 0.155357 |

The Knowledge Graph achieved the highest Top-5 result on the current synthetic test dataset.

The Hybrid Recommender is still used in the application because the research design combines multiple complementary sources of evidence rather than relying on only one recommendation method.

These results are development results based on synthetic data and should not be interpreted as final industry performance.

---

# How to Run the Application

## 1. Clone the Repository

```bash
git clone https://github.com/Sagooparneet/task-allocation-recommender.git
```

Move into the project folder:

```bash
cd task-allocation-recommender
```

---

## 2. Create a Virtual Environment

```bash
python -m venv venv
```

---

## 3. Activate the Virtual Environment

For Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
venv\Scripts\Activate.ps1
```

---

## 4. Install Required Packages

```bash
pip install -r requirements.txt
```

---

## 5. Create and Seed the Database

```bash
python seed.py
```

This creates the development SQLite database and inserts sample users, agents, tasks and skills.

---

## 6. Run the Application

```bash
python run.py
```

---

## 7. Open the Application

Open:

```text
http://127.0.0.1:5000
```

in a web browser.

---

# Development Test Accounts

## Supervisor

```text
Email: supervisor@example.com
Password: password123
```

## Onboarding Agent

```text
Email: grace@example.com
Password: password123
```

## Administrator

```text
Email: admin@example.com
Password: password123
```

These accounts are provided only for development and demonstration.

---

# Automated Testing

The project uses `pytest` for automated application testing.

The tests use a separate temporary SQLite database so that testing does not modify the normal application database.

Run the full automated test suite using:

```bash
python -m pytest -v
```

Current result:

```text
16 passed
```

The tests currently cover authentication, input validation, task creation, recommendation generation, recommendation score validation, unavailable-agent exclusion, successful assignment, duplicate assignment prevention, role restrictions and task completion.

SQLAlchemy legacy API warnings may currently appear during testing. These are deprecation warnings and do not represent failed tests.

---

# Project Structure

```text
intelligent-task-allocation/
│
├── app/
│   ├── admin/
│   ├── agent/
│   ├── auth/
│   ├── models/
│   ├── services/
│   ├── static/
│   ├── supervisor/
│   └── templates/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── experiments/
│
├── notebooks/
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_workflow.py
│
├── config.py
├── requirements.txt
├── run.py
├── seed.py
└── README.md
```

---

# Reproducibility

For reproducible development:

```text
1. Clone the correct Git commit.
2. Create a clean Python virtual environment.
3. Install dependencies from requirements.txt.
4. Use the prepared dataset split.
5. Use random seed 42.
6. Execute notebooks in numerical order.
7. Use validation data for development decisions.
8. Keep the test dataset reserved for final evaluation.
9. Use the fixed Hybrid weights of 30% CBF, 30% CF and 40% KG.
10. Run pytest to verify the Flask application workflow.
```

Important experiment information such as model weights, metrics, predictions and run identifiers should be retained together with the corresponding Git commit and dataset version.

---

# Current Limitations

The current implementation has several limitations.

The model evaluation currently uses synthetic development data rather than final industry operational data.

The Flask application's database contains less historical information than the research datasets. For example, it does not currently store detailed performance ratings for every completed historical assignment.

Because of this, the recommendation service used by the Flask application is an adaptation of the research model rather than an exact reproduction of every notebook feature.

Collaborative Filtering may also have limited historical evidence in a newly seeded application database. A neutral fallback is therefore used when sufficient history is unavailable.

The current SQLite database is appropriate for prototype development but would need to be replaced or extended for a production deployment.

Future evaluation should rerun the complete pipeline using cleaned industry data before making conclusions about real-world recommendation performance.

---

# Project Status

The current prototype supports the main end-to-end task allocation workflow:

```text
Task Creation
→ Recommendation
→ Explanation
→ Supervisor Decision
→ Assignment
→ Agent Completion
→ Status Update
```

The next stages focus on continued interface improvement, documentation, reproducibility and evaluation using industry data when it becomes available.