import streamlit as st
import pandas as pd

st.title("🏀 NBA Prediction App")

# About page
st.header("About Me & This Project")
st.write("This app predicts NBA team wins using historical data and ML models.")

# Team selector
team = st.selectbox("Select a Team:", ["Boston Celtics", "Chicago Bulls", "Lakers"])

# Prediction display (example)
predicted_wins = 50
st.metric(label="Predicted Wins", value=predicted_wins, delta=predicted_wins - 41)
