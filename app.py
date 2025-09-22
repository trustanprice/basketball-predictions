import streamlit as st
import pandas as pd
from src.data_loader import load_final_results, HEADSHOT_PATH, LOGO_PATH

# ----------------------
# Load data
# ----------------------
results_df = load_final_results()

# ----------------------
# Streamlit App
# ----------------------
st.title("🏀 NBA Prediction App")

# --- About Section ---
st.header("About Me & This Project")

# Put two images side by side
col1, col2 = st.columns([1, 1])
with col1:
    st.image(HEADSHOT_PATH, caption="Me", width=200)
with col2:
    st.image(LOGO_PATH, caption="My Favorite Team", width=300)

st.write("""
Hello everyone! My name is **Trustan Price** and I am a Statistics major at the University of Illinois 
with minors in Computer Science and Data Science.  

My motivation for this project stems from my love of sports. Having played varsity basketball, football, 
and baseball all through high school, my passion for sports has always been strong and it still hasn’t left.  
I decided to start this project when I realized that most of my projects were built to impress recruiters 
and hiring managers, not to genuinely amuse me.  

I thought to myself: **"How driven would I be to complete a project about a topic I truly love?"**  
Since I’ve always enjoyed analyzing and crunching numbers (something I did in my free time as a kid), 
this project felt like the perfect fit.  

What you see here is the result, a rough draft of a prediction model that will eventually become 
a **failure model** once the 2025–2026 NBA season begins.  

As of now, this webpage is powered by **Streamlit**, while most of the backend code lives in Jupyter notebooks 
and is gradually being moved into Python scripts. All of the data was scraped from **Basketball Reference** 
and **NBA.com**, then cleaned and preprocessed for us to explore together.  

For the modeling, I used **Elastic Net regression** to perform feature reduction and identify the most important 
predictors of team success. After narrowing down the features, I applied a **KNN Regressor** to generate the 
predicted win totals for each team.

If you also share a love for basketball data, check out the code on my GitHub:  
👉 [trustanprice/basketball-predictions](https://github.com/trustanprice/basketball-predictions)  

Go ahead and pick your favorite team from the dropdown menu, and I hope you enjoy!
""")

# ----------------------
# Predictions Section
# ----------------------
if "show_predictions" not in st.session_state:
    st.session_state.show_predictions = False

if st.button("Start Predicting"):
    st.session_state.show_predictions = True

if st.session_state.show_predictions:
    st.subheader("🔮 Team Win Predictions")
    st.write("Select a team below to see their predicted wins and the key stats driving the model.")

    # Get unique teams
    teams = sorted(results_df["Team"].unique())
    team = st.selectbox("Select a Team:", teams)

    # Pick latest season
    latest_season = results_df["Season"].max()
    team_row = results_df[
        (results_df["Season"] == latest_season) & (results_df["Team"] == team)
    ]

    if not team_row.empty:
        actual_wins = team_row["W"].values[0]
        predicted_wins = team_row["Pred_NWins"].values[0]

        st.metric(
            label=f"{team} Predicted Wins ({latest_season})",
            value=int(predicted_wins),
            delta=int(predicted_wins - actual_wins),
        )

        st.subheader("📊 Key Features Driving Prediction")
        feature_cols = [
            col
            for col in team_row.columns
            if col not in ["Season", "Team", "W", "Pred_NWins"]
        ]
        feature_data = team_row[feature_cols].T.reset_index()
        feature_data.columns = ["Feature", "Value"]
        st.table(feature_data)
    else:
        st.warning(f"No data available for {team} in {latest_season}.")
