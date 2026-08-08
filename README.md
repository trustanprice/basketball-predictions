# 🏀 Basketball Prediction Project  

This project explores NBA team performance and develops predictive models to understand **team success and failure**.  
Using historical data from **2016–2025**, the project integrates multiple dimensions of team information — from records and payroll to draft picks, coaching, and player stats — to create a comprehensive dataset for analysis and modeling.  

👉 Live Demo: [Streamlit App](https://basketball-predictions-trustanprice.streamlit.app/)

👉 Codebase: [GitHub Repo](https://github.com/trustanprice/basketball-predictions)

---

## Project Structure  

This project is growing beyond the original win-total model — see [`AGENTS.md`](AGENTS.md) for
the full module breakdown (win model / live player ratings / coaching evaluation) and the
per-directory docs it links to.

BASKETBALL-PREDICTIONS
│

├── data/ # Static, historical (2016–2025) datasets — see data/AGENTS.md

│ ├── raw/

│ └── processed/

│

├── backend/ # All Python — see backend/AGENTS.md

│ ├── win_model/ # Load, features, and the win-total model (formerly src/)

│ ├── live_client/ # NBA.com live data client (new)

│ ├── ratings/ # Player power rankings + coaching eval (new)

│ ├── api/ # API serving the above to the frontend (not yet built)

│ ├── notebooks/ # Jupyter notebooks (data cleaning, exploration, modeling)

│ ├── tests/

│ └── requirements.txt

│

├── frontend/ # Next.js app (not yet scaffolded) — see frontend/AGENTS.md

│

├── app.py # Streamlit app — transitional, stays at repo root for the

│ # existing Streamlit Cloud deployment until frontend/ replaces it

├── requirements.txt # Pointer to backend/requirements.txt (keeps Streamlit Cloud working)

├── .gitignore

└── README.md # Project overview (this file)

---


---

## Data Sources  

The project integrates multiple cleaned datasets into a **master dataframe**:  

- **Team stats & records** (`team-stats.csv`, `team-records.csv`)  
  - Season results, home/road splits, pre/post All-Star splits, win %  
- **Payroll data** (`team-payroll.csv`)  
  - Team salary data from 2016–2025  
- **Coaching data** (`coach.csv`)  
  - Coaching tenure, win/loss records, and number of coaches per season  
- **Draft data** (`draft.csv`)  
  - Draft picks with season/year alignment  
- **Strength of Schedule (SOS)** (`team-sos.csv`)  
  - Calculated using opponent win percentages  
- **Player stats (top 10 players per team)**  
  - Includes GP (games played) to infer injuries and availability  

---

## Setup  

### 1. Clone the repo
```bash
git clone https://github.com/your-username/BASKETBALL-PREDICTION.git
cd BASKETBALL-PREDICTION
```
---

### 2. Create and activate a virtual environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
.\venv\Scripts\activate       # Windows
cd ..
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Usage

- Data Cleaning: Run 01_data_cleaning.ipynb to check for NaN values, duplicates, and validate team/season consistency.
- Exploration: Use 02_exploration.ipynb to generate summary statistics and exploratory visualizations to understand data trends.
- Modeling: Train predictive models in 03_failure_model.ipynb to analyze team success/failure using regression and machine learning.
- Outputs: Figures, reports, and model artifacts are stored in outputs/.

To run Jupyter notebooks:
```bash
jupyter notebook
```

---

## Goals

- Analyze win/loss trends across multiple seasons
- Incorporate front office factors (payroll, draft, coaches)
- Integrate player stats to capture injuries/availability
- Build a failure model to predict team underperformance (e.g., missing playoffs, low win totals)
- Visualize and interpret the results

---

## Tech Stack

- Python 3.9+
- pandas, numpy
- matplotlib, seaborn
- scikit-learn (for modeling)
- Jupyter Notebook

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change.

---

## License & Attribution

Data collected from basketball-reference.com and nba.com for educational purposes.
