# 🏀 Basketball Prediction Project

This project explores NBA team records and develops a **failure model** for wins and losses using historical data (2015–2025).  
The goal is to analyze team performance trends, identify conditions that lead to failure (e.g., missing playoffs, low win totals), and build predictive models for future seasons.

---

## 📂 Project Structure

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
│ └── models/ # Saved models
│
├── requirements.txt # Python dependencies
├── .gitignore # Files to ignore in git
└── README.md # Project overview (this file)

---

## 📊 Data

The primary dataset is `team-records.csv`, which contains season-by-season NBA team records and splits.  
Columns include:

- **Team information**: `Team`, `Year`, `Rk`
- **Overall record**: `Overall`, `Home`, `Road`
- **Conference/Division splits**: `E`, `W`, `A`, `C`, `SE`, `NW`, `P`, `SW`
- **All-Star break splits**: `Pre`, `Post`
- **Margin splits**: `≤3`, `≥10`
- **Monthly records**: `Oct`, `Nov`, `Dec`, `Jan`, `Feb`, `Mar`, `Apr`

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/your-username/BASKETBALL-PREDICTION.git
cd BASKETBALL-PREDICTION
```

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

Exploration: Start with the notebooks in notebooks/

Data processing: Use functions in src/data_loader.py to load and clean datasets

Modeling: Build and train failure models with src/model.py

Outputs: Plots and saved models are stored in outputs/

To run Jupyter notebooks:
```bash
jupyter notebook
```

---

## Goals

Analyze win/loss trends across multiple seasons

Develop a survival/failure model for NBA teams

Predict probability of failure (e.g., missing playoffs, failing to reach a win threshold)

Visualize results through plots and reports

---

## Tech Stack

Python 3.9+

pandas, numpy

matplotlib, seaborn

scikit-learn (for modeling)

Jupyter Notebook

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change.

---

## License

https://www.basketball-reference.com/ was used for this project.
