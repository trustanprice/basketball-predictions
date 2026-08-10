import streamlit as st
import pandas as pd
from backend.win_model.data_loader import load_final_results, load_model_metadata, HEADSHOT_PATH, LOGO_PATH
from PIL import Image
from pathlib import Path

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

col1, col2 = st.columns([1, 1])

with col1:
    if Path(HEADSHOT_PATH).exists():
        st.image(Image.open(HEADSHOT_PATH), caption="Me", width=200)
    else:
        st.warning(f"Headshot not found: {HEADSHOT_PATH}")

with col2:
    if Path(LOGO_PATH).exists():
        st.image(Image.open(LOGO_PATH), caption="My Favorite Team", width=300)
    else:
        st.warning(f"Logo not found: {LOGO_PATH}")
        
        
st.write("""
Hello everyone! My name is **Trustan Price** and I am currently a Master's student in Computer Science 
at the University of Illinois, with a Bachelor's degree in Statistics and minor in Data Science.

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

For the modeling, I benchmark a **KNN Regressor** against a **monotonic-constrained gradient-boosted regressor**
using season-grouped walk-forward validation (train on seasons ≤ N, validate on season N+1, roll forward — no
random cross-validation folds, which would leak future seasons into training) and keep whichever wins on
out-of-sample error. Every prediction ships with an 80% prediction interval and an expandable "how this was
calculated" breakdown — see the Predictions section below.

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
    # Pick latest season — this is always the live forecast row: last season's
    # completed stats projecting a season that hasn't been played yet, so it has
    # no actual win total to compare against.
    latest_season = results_df["Season"].max()

    st.subheader(f"{latest_season} Team Win Predictions")
    st.write("Select a team below to see their predicted wins, with an 80% prediction interval.")

    # Get unique teams
    teams = sorted(results_df["Team"].unique())
    team = st.selectbox("Select a Team:", teams)

    team_row = results_df[
        (results_df["Season"] == latest_season) & (results_df["Team"] == team)
    ]

    if not team_row.empty:
        predicted_wins = team_row["Pred_Wins"].values[0]
        lower = team_row["Pred_Wins_Lower"].values[0]
        upper = team_row["Pred_Wins_Upper"].values[0]
        actual_wins = team_row["W"].values[0]

        st.metric(
            label=f"{team} Predicted Wins ({latest_season})",
            value=f"{predicted_wins:.0f}",
            delta=None if pd.isna(actual_wins) else int(predicted_wins - actual_wins),
        )
        st.caption(f"80% prediction interval: {lower:.0f}–{upper:.0f} wins")

        metadata = load_model_metadata()
        with st.expander("How this was calculated"):
            mc = metadata["model_comparison"]
            st.markdown(f"""
**Validation method:** {metadata['validation_method']}

**Target:** {metadata['target_definition']}

**Model selection:** Two candidates — {mc['candidates'][0]} and {mc['candidates'][1]} —
were each hyperparameter-tuned using walk-forward CV, then compared on their
walk-forward mean absolute error (out-of-sample, never in-sample fit) across
{mc['n_walk_forward_folds']} rolling folds:

| Candidate | Walk-forward MAE |
|---|---|
| KNN | {mc['knn_walk_forward_mae']} wins |
| GBM (monotonic) | {mc['gbm_walk_forward_mae']} wins |

**Winner:** {mc['winner'].upper()}, with hyperparameters
`{metadata['winning_model']['best_params']}`.
""")
            if metadata["winning_model"]["monotonic_increasing_features"]:
                st.write(
                    "Monotonic constraint: predicted wins can never *decrease* as "
                    + " or ".join(metadata["winning_model"]["monotonic_increasing_features"])
                    + " increases, all else equal — prevents the model from learning a "
                      "locally spurious inverse relationship out of a small, noisy dataset."
                )

            st.write(f"**Prediction interval:** {metadata['prediction_interval']['method']} "
                      f"({metadata['prediction_interval']['coverage']} coverage).")

            calibration = metadata.get("calibration")
            if calibration:
                st.write("**Calibration:**", calibration["description"])
                st.write(
                    f"Walk-forward MAE — uncalibrated: {calibration['walk_forward_mae_uncalibrated']} wins, "
                    f"calibrated: {calibration['walk_forward_mae_calibrated']} wins."
                )
                st.caption(calibration["note"])

            st.write("**Top features by permutation importance** (how much walk-forward "
                      "MAE gets worse when a feature is shuffled — bigger is more important):")
            importance_df = pd.DataFrame(metadata["top_feature_importance"])
            st.dataframe(importance_df, hide_index=True)

            feature_notes = metadata.get("feature_notes", {})
            if feature_notes:
                st.write("**Notes on specific features** (so a bare column name isn't mistaken "
                          "for something it isn't):")
                for feature, note in feature_notes.items():
                    st.caption(f"**{feature}** — {note}")

            st.caption(
                f"Trained on {metadata['n_training_rows']} team-seasons "
                f"({metadata['n_teams']} teams, feature seasons "
                f"{min(metadata['feature_seasons_used'])}–{max(metadata['feature_seasons_used'])}). "
                f"Generated {metadata['generated_at']}."
            )
    else:
        st.warning(f"No data available for {team} in {latest_season}.")

# ----------------------
# Accuracy Section
# ----------------------
st.header("Model Accuracy Results")
st.subheader("GOAL: 85% Accuracy at ±5 Game Threshold")

def display_accuracy(season: int, threshold: int, comments: str):
    season_df = results_df[results_df["Season"] == season].copy()

    if "Pred_Wins" in season_df.columns:
        if "within_threshold" not in season_df.columns:
            # fallback if not precomputed
            season_df["within_threshold"] = (
                (season_df["Pred_Wins"] - season_df["W"]).abs() <= threshold
            )
        accuracy = season_df["within_threshold"].mean()

        st.subheader(f"{season} Season Accuracy (±{threshold} Wins)")
        st.metric("Accuracy", f"{accuracy:.2%}")
        st.dataframe(season_df[["Team", "W", "Pred_Wins", "within_threshold"]])

        st.write(f"✍️ *Comments:* {comments}")
    else:
        st.warning(f"No `Pred_Wins` column available for {season}.")

# --- Buttons ---
if st.button("View 2024 Accuracy"):
    display_accuracy(
        2024,
        threshold=5,
        comments = (
    "This is walk-forward backtested accuracy: the model was trained only on seasons "
    "before 2024 and never saw 2024 data during training or tuning. It's noticeably below "
    "the 85% goal — that's expected and, honestly, more trustworthy than the old number. "
    "The previous version of this model trained on same-season stats to predict that same "
    "season's win total, which was close to circular for historical rows and looked far "
    "more accurate than it really was. This number reflects genuine predictive difficulty, "
    "not a regression."
)
    )

if st.button("View 2025 Accuracy"):
    display_accuracy(
        2025,
        threshold=5,
        comments = (
    "Same walk-forward backtest, for 2025. Next steps for closing the gap toward the 85% "
    "goal: the current feature set is unchanged from the old model (Phase 1 only fixed "
    "validation methodology, model choice, and interval estimation) — roster-change context "
    "(trades, free agency) and the live player ratings from Phase 2+ are the more promising "
    "levers than further tuning KNN or GBM hyperparameters on this same feature set."
)
    )

