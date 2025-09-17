# 🏀 Basketball Prediction Project  

This project explores NBA team performance and develops predictive models to understand **team success and failure**.  
Using historical data from **2016–2025**, the project integrates multiple dimensions of team information — from records and payroll to draft picks, coaching, and player stats — to create a comprehensive dataset for analysis and modeling.  

---

## Project Structure  

BASKETBALL-PREDICTION
│

├── data/ # Datasets

│ ├── raw/ # Original CSVs (e.g., per-season records)

│ └── processed/ # Cleaned & merged data with Year column

│

├── notebooks/ # Jupyter notebooks

│ ├── 01_data_cleaning.ipynb

│ ├── 02_exploration.ipynb

│ └── 03_failure_model.ipynb

│

├── src/ # Source code

│ ├── data_loader.py # Load & preprocess datasets

│ ├── features.py # Feature engineering (streaks, margins, etc.)

│ ├── model.py # Failure model implementation

│ └── utils.py # Helper functions

│

├── outputs/ # Model outputs

│ ├── figures/ # Graphs and plots

│

├── requirements.txt # Python dependencies

├── .gitignore # Files to ignore in git

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
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
.\venv\Scripts\activate       # Windows
```

### 3. Install Dependencies
pip install -r requirements.txt

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
