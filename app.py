"""Minimal Streamlit landing page; dashboard comes after the solver works."""

import streamlit as st

st.set_page_config(page_title="CompuOpti", page_icon="📊", layout="wide")
st.title("CompuOpti")
st.caption("Multi-objective project selection and employee scheduling")

st.info(
    "Starter interface. First validate the input data and implement/test the MILP. "
    "Schedule tables, objective comparisons, and Pareto visualizations will be added next."
)

st.subheader("Planned workflow")
st.markdown(
    "1. Load an instance\n"
    "2. Validate employees, qualifications, projects, and deadlines\n"
    "3. Run the MILP / epsilon-constraint procedure\n"
    "4. Compare non-dominated schedules"
)
