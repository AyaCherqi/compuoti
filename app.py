"""CompuOpti | Interactive exploration of saved epsilon-constraint results.

Run from the repository root:
    streamlit run app.py

The dashboard reads results/*_pareto.json and data/instances/*.json.
It does not require Gurobi to display existing optimization results.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
DATA_DIR = ROOT / "data" / "instances"

NAVY = "#162440"
TEAL = "#0A9285"
CYAN = "#1FA3C5"
AMBER = "#E7A139"
RED = "#D45868"
GRAY = "#8A9AAF"
PROJECT_COLORS = [
    "#1C8E87", "#5678CF", "#E3A34B", "#B679CA", "#D66C76",
    "#569FC5", "#86AA5E", "#C68457", "#697CC0", "#9C8C62",
    "#7B9AB0", "#DD839A", "#43A39A", "#A49AD2", "#E7AE66",
    "#66A3C3", "#A4B873", "#C48DB7", "#6D8C9B", "#A88576",
]

OBJECTIVES = {
    "financial": ("Net gain", "↑ maximize"),
    "completion": ("Completion score", "↓ minimize"),
    "relationships": ("Staff–project links", "↓ minimize"),
    "late_projects": ("Late projects", "↓ minimize"),
}


def load_json(path: Path) -> dict[str, Any]:
    """Read one JSON document."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The JSON root must be an object.")
    return data


def validate_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return saved solutions, or raise a readable schema error."""
    solutions = data.get("solutions")
    if not isinstance(solutions, list):
        raise ValueError("This is not a CompuOpti Pareto result: missing 'solutions' list.")
    for number, solution in enumerate(solutions, start=1):
        if not isinstance(solution, dict):
            raise ValueError(f"Solution {number} is not a JSON object.")
        values = solution.get("objective_values")
        if not isinstance(values, dict) or any(k not in values for k in OBJECTIVES):
            raise ValueError(f"Solution {number} is missing objective values.")
        if not isinstance(solution.get("assignments"), list):
            raise ValueError(f"Solution {number} has no 'assignments' list.")
        if not isinstance(solution.get("projects"), list):
            raise ValueError(f"Solution {number} has no 'projects' list.")
    return solutions


def objective_table(solutions: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per nondominated objective vector."""
    rows = []
    for i, solution in enumerate(solutions, 1):
        obj = solution["objective_values"]
        projects = solution.get("projects", [])
        rows.append({
            "Solution": f"S{i}",
            "Net gain": float(obj["financial"]),
            "Completion score": float(obj["completion"]),
            "Staff–project links": float(obj["relationships"]),
            "Late projects": float(obj["late_projects"]),
            "Projects selected": sum(bool(p.get("selected")) for p in projects),
            "Assigned days": len(solution.get("assignments", [])),
        })
    return pd.DataFrame(rows)


def match_instance(result_path: Path) -> dict[str, Any] | None:
    """Find a course instance matching e.g. toy_pareto.json -> toy_instance.json."""
    name = result_path.stem
    if not name.endswith("_pareto"):
        return None
    stem = name[: -len("_pareto")]
    candidate = DATA_DIR / f"{stem}_instance.json"
    try:
        return load_json(candidate) if candidate.exists() else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def project_details(solution: dict[str, Any], instance: dict[str, Any] | None) -> pd.DataFrame:
    """Combine solver output with gains and penalties from the original instance."""
    jobs = (instance or {}).get("jobs", [])
    jobs_by_name = {job.get("name"): job for job in jobs}
    rows = []
    for project in solution["projects"]:
        selected = bool(project.get("selected", False))
        project_id = project.get("project_id")
        job = (
            jobs[project_id]
            if isinstance(project_id, int) and 0 <= project_id < len(jobs)
            else jobs_by_name.get(project.get("project_name"), {})
        )
        if not isinstance(job, dict) or job.get("name") != project.get("project_name"):
            job = jobs_by_name.get(project.get("project_name"), {})
        late_days = int(round(float(project.get("late_days") or 0)))
        gain = float(job["gain"]) if "gain" in job else None
        penalty_per_day = float(job["daily_penalty"]) if "daily_penalty" in job else None
        rows.append({
            "Project": project.get("project_name", str(project_id)),
            "Selected": selected,
            "Status": "Late" if selected and late_days else "On time" if selected else "Rejected",
            "Deadline": int(project.get("due_date", 0)),
            "Completed": int(round(float(project.get("completion_day") or 0))) if selected else None,
            "Late days": late_days if selected else 0,
            "Employees": ", ".join(project.get("assigned_employees") or []),
            "Gross gain": gain if selected and gain is not None else 0.0 if gain is not None else None,
            "Late penalty": late_days * penalty_per_day if penalty_per_day is not None else None,
        })
    return pd.DataFrame(rows)


def schedule_matrix(
    solution: dict[str, Any], instance: dict[str, Any] | None
) -> tuple[list[str], list[int], list[list[int]], list[list[str]], list[list[str]], list[str]]:
    """Produce employee × day colors, abbreviations, and hover descriptions.

    Color code 0 = unassigned; 1 = vacation; 2+ = a selected project.
    """
    assignments = solution.get("assignments", [])
    staff = (instance or {}).get("staff", [])
    employees = [str(e.get("name")) for e in staff]
    for name in sorted({str(a.get("employee_name")) for a in assignments}):
        if name not in employees:
            employees.append(name)

    horizon = int((instance or {}).get("horizon") or max(
        [int(a.get("day", 0)) for a in assignments] +
        [int(p.get("due_date", 0)) for p in solution.get("projects", [])] + [1]
    ))
    days = list(range(1, max(horizon, 1) + 1))

    ordered_projects = list(dict.fromkeys(
        str(a.get("project_name")) for a in assignments
    ))
    project_codes = {p: idx + 2 for idx, p in enumerate(ordered_projects)}
    names_to_index = {name: idx for idx, name in enumerate(employees)}
    vacation_days = {
        name: {int(day) for day in e.get("vacations", [])}
        for name, e in zip(employees[: len(staff)], staff)
    }

    z = [[0 for _ in days] for _ in employees]
    text = [["" for _ in days] for _ in employees]
    hover = [["Free / unassigned" for _ in days] for _ in employees]

    for name, days_off in vacation_days.items():
        if name not in names_to_index:
            continue
        row = names_to_index[name]
        for day in days_off:
            if 1 <= day <= horizon:
                z[row][day - 1] = 1
                text[row][day - 1] = ""
                hover[row][day - 1] = "Vacation / unavailable"

    for assignment in assignments:
        day = int(assignment.get("day", 0))
        name = str(assignment.get("employee_name"))
        project = str(assignment.get("project_name"))
        if name not in names_to_index or day not in days:
            continue
        row, col = names_to_index[name], day - 1
        z[row][col] = project_codes[project]
        text[row][col] = str(assignment.get("qualification", ""))
        hover[row][col] = f"{project} · Skill {assignment.get('qualification', '?')}"

    return employees, days, z, text, hover, ordered_projects


def heatmap_figure(
    solution: dict[str, Any], instance: dict[str, Any] | None
) -> go.Figure:
    employees, days, z, labels, descriptions, projects = schedule_matrix(solution, instance)
    colors = ["#E9EFF5", "#D7DBE2"] + [
        PROJECT_COLORS[i % len(PROJECT_COLORS)] for i in range(len(projects))
    ]
    steps = []
    for idx, color in enumerate(colors):
        steps.extend([(idx / len(colors), color), ((idx + 1) / len(colors), color)])

    fig = go.Figure(go.Heatmap(
        x=days, y=employees, z=z, text=labels, customdata=descriptions,
        colorscale=steps, zmin=-0.5, zmax=len(colors) - 0.5,
        showscale=False, xgap=2, ygap=3,
        hovertemplate="<b>%{y}</b> · Day %{x}<br>%{customdata}<extra></extra>",
        texttemplate="%{text}" if len(days) <= 25 else None,
        textfont={"size": 11, "color": "white"},
    ))
    for index, project in enumerate(projects[:12]):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", showlegend=True, name=project,
            marker={"size": 11, "color": PROJECT_COLORS[index % len(PROJECT_COLORS)],
                    "symbol": "square"}, hoverinfo="skip",
        ))
    fig.update_layout(
        height=max(300, min(780, 165 + len(employees) * 46)),
        margin={"l": 10, "r": 14, "t": 24, "b": 24},
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis={"title": "Working day", "side": "top", "dtick": 1 if len(days) <= 25 else 2,
               "tickmode": "linear", "tick0": 1, "fixedrange": True},
        yaxis={"title": "", "autorange": "reversed", "fixedrange": True},
        legend={"orientation": "h", "y": -0.15, "x": 0, "font": {"size": 10}},
        font={"family": "Arial", "color": NAVY},
    )
    return fig


def pareto_figure(frame: pd.DataFrame, x: str, y: str, chosen: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=frame[x], y=frame[y], mode="markers+text",
        text=frame["Solution"], textposition="top center",
        customdata=frame[["Staff–project links", "Late projects", "Projects selected"]].to_numpy(),
        marker={"size": 17, "color": frame["Late projects"], "colorscale": [
            [0, TEAL], [0.5, CYAN], [1, AMBER]
        ], "showscale": True, "colorbar": {"title": "Late"},
            "line": {"color": "white", "width": 2}},
        hovertemplate=(
            "<b>%{text}</b><br>" + x + ": %{x:.2f}<br>" + y + ": %{y:.2f}"
            "<br>Relationships: %{customdata[0]:.0f}"
            "<br>Late projects: %{customdata[1]:.0f}"
            "<br>Selected projects: %{customdata[2]:.0f}<extra></extra>"
        ),
        name="Pareto candidates",
    ))
    selected = frame[frame["Solution"] == chosen]
    if not selected.empty:
        fig.add_trace(go.Scatter(
            x=selected[x], y=selected[y], mode="markers",
            marker={"size": 29, "color": "rgba(0,0,0,0)",
                    "line": {"color": NAVY, "width": 3}},
            hoverinfo="skip", showlegend=False,
        ))
    fig.update_layout(
        height=480, template="plotly_white", margin={"l": 10, "r": 20, "t": 20, "b": 10},
        xaxis_title=x, yaxis_title=y, font={"color": NAVY},
    )
    return fig


def relative_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert the sampled extremes into comparable 0–100 benefit scores.

    These are *relative to the loaded sample*, not absolute quality measures.
    """
    columns = ["Net gain", "Completion score", "Staff–project links", "Late projects"]
    normalized = pd.DataFrame({"Solution": frame["Solution"]})
    for column in columns:
        values = frame[column].astype(float)
        lo, hi = values.min(), values.max()
        if abs(hi - lo) < 1e-10:
            normalized[column] = 100.0
        elif column == "Net gain":
            normalized[column] = 100.0 * (values - lo) / (hi - lo)
        else:
            normalized[column] = 100.0 * (hi - values) / (hi - lo)
    return normalized


def radar_figure(frame: pd.DataFrame, first: str, second: str | None) -> go.Figure:
    normalized = relative_scores(frame).set_index("Solution")
    dimensions = ["Net gain", "Completion score", "Staff–project links", "Late projects"]
    labels = ["Higher gain", "Earlier completion", "Fewer links", "Less lateness"]
    fig = go.Figure()
    for label, color in [(first, TEAL), (second, AMBER)]:
        if not label or label not in normalized.index or (label == second and first == second):
            continue
        values = normalized.loc[label, dimensions].to_list()
        fig.add_trace(go.Scatterpolar(
            r=values + values[:1], theta=labels + labels[:1],
            mode="lines+markers", fill="toself", name=label,
            line={"color": color, "width": 3}, fillcolor=(
                "rgba(10,146,133,0.15)" if color == TEAL else "rgba(231,161,57,0.14)"
            ),
        ))
    fig.update_layout(
        height=410, margin={"l": 25, "r": 25, "t": 30, "b": 15},
        polar={"radialaxis": {"visible": True, "range": [0, 100], "ticksuffix": "%"}},
        showlegend=True, paper_bgcolor="white", font={"color": NAVY},
    )
    return fig


def completion_figure(frame: pd.DataFrame) -> go.Figure:
    """Compare deadlines with completed dates for executed projects."""
    selected = frame[frame["Selected"]].copy()
    if selected.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_bar(
        x=selected["Project"], y=selected["Deadline"],
        name="Deadline", marker_color="#B8C5D2",
    )
    fig.add_bar(
        x=selected["Project"], y=selected["Completed"],
        name="Actual completion", marker_color=[
            RED if v > due else TEAL
            for v, due in zip(selected["Completed"], selected["Deadline"])
        ],
    )
    fig.update_layout(
        barmode="group", height=370, template="plotly_white",
        margin={"l": 5, "r": 10, "t": 15, "b": 15},
        yaxis_title="Working day", xaxis_title="Project",
        legend={"orientation": "h", "y": 1.15}, font={"color": NAVY},
    )
    return fig


def employee_utilization(
    solution: dict[str, Any], instance: dict[str, Any] | None
) -> pd.DataFrame:
    """Calculate booked and available days; unavailable if no instance file."""
    if not instance or not instance.get("staff") or not instance.get("horizon"):
        return pd.DataFrame()
    counts = Counter(a.get("employee_name") for a in solution["assignments"])
    rows = []
    horizon = int(instance["horizon"])
    for person in instance["staff"]:
        name = person["name"]
        leave = {int(day) for day in person.get("vacations", []) if 1 <= int(day) <= horizon}
        available = horizon - len(leave)
        booked = counts.get(name, 0)
        rows.append({"Employee": name, "Assigned days": booked,
                     "Available days": available,
                     "Utilization %": 100.0 * booked / available if available > 0 else 0.0})
    return pd.DataFrame(rows)


def section_intro(title: str, description: str) -> None:
    st.subheader(title)
    st.caption(description)


def main() -> None:
    st.set_page_config(page_title="CompuOpti | Decision Lab", page_icon="🧩", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(
        """<style>
        .block-container {max-width: 1420px; padding-top: 1.45rem; padding-bottom: 2.5rem;}
        [data-testid="stMetric"] {background: #F3F7FB; border: 1px solid #E2EAF1;
            padding: 0.9rem 1.05rem; border-radius: 14px;}
        [data-testid="stMetricLabel"] {color: #566881;}
        [data-testid="stMetricValue"] {color: #172844;}
        .co-hero {background: linear-gradient(115deg, #142B45 0%, #194E66 65%, #137C80 100%);
            border-radius: 18px; padding: 24px 30px; color: white; margin-bottom: 18px;}
        .co-kicker {letter-spacing: .15em; font-size: 12px; font-weight: 750;
            color: #93E0DC; text-transform: uppercase;}
        .co-hero h1 {color: white; font-size: 2.15rem; margin: 0.3rem 0;}
        .co-hero p {color: #DCECF3; margin-bottom: 0; font-size: 15px;}
        .co-note {background: #EFF7F7; border-left: 4px solid #0A9285;
            padding: 11px 14px; border-radius: 5px; color: #22435B; font-size: 14px;}
        </style>""", unsafe_allow_html=True,
    )
    st.markdown(
        """<div class="co-hero"><div class="co-kicker">Decision intelligence / CompuOpti</div>
        <h1>Project portfolio & workforce planner</h1>
        <p>Explore Pareto trade-offs, compare competing schedules, and see who works on what day.</p>
        </div>""", unsafe_allow_html=True,
    )

    files = sorted(RESULTS_DIR.glob("*_pareto.json"))
    st.sidebar.header("Explore results")
    if not files:
        st.error("No results found in `results/`. Generate an epsilon-constraint result first.")
        st.code("python -m compuoti.multiobjective --instance data/instances/toy_instance.json "
                "--grid-levels 3 --min-selected 1 --output results/toy_pareto.json")
        st.stop()

    chosen_path = st.sidebar.selectbox(
        "Saved experiment", files,
        format_func=lambda p: p.stem.replace("_pareto", "").replace("_", " ").title(),
    )
    uploaded = st.sidebar.file_uploader("Or upload another Pareto JSON", type=["json"])
    try:
        if uploaded is not None:
            data = json.loads(uploaded.getvalue().decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("The uploaded JSON must be an object.")
            source_label = uploaded.name
            instance = match_instance(Path(uploaded.name))
        else:
            data = load_json(chosen_path)
            source_label = chosen_path.name
            instance = match_instance(chosen_path)
        solutions = validate_results(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        st.error(f"Unable to display results: {exc}")
        st.stop()

    if not solutions:
        st.warning("This result has no saved nondominated solutions.")
        st.stop()

    table = objective_table(solutions)
    choice = st.sidebar.selectbox(
        "Highlighted solution", range(len(solutions)),
        format_func=lambda ix: (
            f"S{ix + 1}  ·  gain {solutions[ix]['objective_values']['financial']:.2f}"
        ),
    )
    selected_label = f"S{choice + 1}"
    current = solutions[choice]
    values = current["objective_values"]
    project_df = project_details(current, instance)

    st.caption(f"SOURCE  /  {source_label}  ·  sampled ε-constraint frontier")
    stats = st.columns(4)
    stats[0].metric("Nondominated solutions", len(solutions))
    stats[1].metric("ε combinations explored", data.get("attempted_combinations", "—"))
    stats[2].metric("Feasible combinations", data.get("successful_combinations", "—"))
    stats[3].metric("Infeasible combinations", data.get("infeasible_combinations", "—"))
    st.markdown(
        '<div class="co-note">Each solution is a complete schedule. '
        'More gain is better; lower completion score, fewer employee–project links, '
        'and fewer late projects are better. The frontier is sampled, not exhaustive.</div>',
        unsafe_allow_html=True,
    )

    tab_overview, tab_pareto, tab_schedule, tab_projects, tab_diagnostics = st.tabs([
        "◈  Overview", "↗  Pareto explorer", "▦  Staff schedule", "▤  Project portfolio",
        "◎  Search details",
    ])

    with tab_overview:
        section_intro(f"Selected portfolio · {selected_label}",
                      "One compromise among the nondominated schedules found by the ε-grid.")
        metrics = st.columns(5)
        metrics[0].metric("Net gain", f"{values['financial']:,.2f}")
        metrics[1].metric("Projects delivered", int(project_df["Selected"].sum()))
        metrics[2].metric("Completion score", f"{values['completion']:,.2f}")
        metrics[3].metric("Staff–project links", f"{values['relationships']:,.0f}")
        metrics[4].metric("Late projects", f"{values['late_projects']:,.0f}")

        left, right = st.columns([1.5, 1], gap="large")
        with left:
            section_intro("Objective space", "Trade-offs between the saved solutions.")
            st.plotly_chart(pareto_figure(table, "Completion score", "Net gain", selected_label),
                            use_container_width=True, key="overview_pareto_chart")
        with right:
            section_intro("Project selection", "Delivered on time, late, or rejected.")
            counts = project_df["Status"].value_counts().reindex(
                ["On time", "Late", "Rejected"], fill_value=0
            )
            donut = go.Figure(go.Pie(
                labels=counts.index, values=counts.values, hole=0.68,
                marker={"colors": [TEAL, RED, "#B7C3D2"]}, sort=False,
                textinfo="label+value",
            ))
            donut.update_layout(
                height=375, margin={"l": 0, "r": 0, "t": 15, "b": 10},
                showlegend=False, paper_bgcolor="white", font={"color": NAVY},
                annotations=[{"text": str(len(project_df)), "x": .5, "y": .5,
                              "showarrow": False, "font": {"size": 29, "color": NAVY}}],
            )
            st.plotly_chart(donut, use_container_width=True, key="overview_project_donut")

        st.markdown("#### All sampled Pareto solutions")
        st.dataframe(table.round(2), use_container_width=True, hide_index=True)
        st.caption("Completion score = sum of completion-day indices for selected projects; "
                   "it is not elapsed duration or makespan. Financial values use the dataset's gain units.")

    with tab_pareto:
        section_intro("Explore objective trade-offs", "Choose any two objectives to display on the axes.")
        xcol, ycol = st.columns(2)
        axis_options = ["Completion score", "Staff–project links", "Late projects", "Net gain"]
        x_axis = xcol.selectbox("Horizontal axis", axis_options, index=0)
        y_axis = ycol.selectbox("Vertical axis", axis_options, index=3)
        if x_axis == y_axis:
            st.info("Choose different axes for a meaningful trade-off chart.")
        else:
            st.plotly_chart(pareto_figure(table, x_axis, y_axis, selected_label),
                            use_container_width=True, key="explorer_pareto_chart")

        left, right = st.columns([1.1, 1], gap="large")
        with left:
            section_intro("Relative strength profile", "100 = best observed value among the loaded solutions.")
            other_index = st.selectbox(
                "Compare highlighted solution with", range(len(solutions)),
                index=(choice + 1) % len(solutions),
                format_func=lambda ix: f"S{ix + 1}",
            )
            second_label = f"S{other_index + 1}"
            st.plotly_chart(radar_figure(table, selected_label, second_label),
                            use_container_width=True, key="explorer_radar_chart")
            st.caption("Radar scores are normalized against this *sample only*; "
                       "they are not a combined optimization objective.")
        with right:
            section_intro("Exact objective values", "The four values used for dominance comparisons.")
            subset = table[["Solution", "Net gain", "Completion score",
                            "Staff–project links", "Late projects"]].round(3)
            st.dataframe(subset, use_container_width=True, hide_index=True)
            st.download_button(
                "Download objective table (CSV)", data=table.to_csv(index=False).encode("utf-8"),
                file_name="compuoti_pareto_objectives.csv", mime="text/csv",
            )

    with tab_schedule:
        section_intro(f"Employee-day assignment map · {selected_label}",
                      "Each colored cell is one employee working on a project; the letter is the skill.")
        employees, days, _, _, _, active_projects = schedule_matrix(current, instance)
        if len(active_projects) > 12:
            st.caption("Only the first 12 project labels appear in the chart legend; "
                       "hover over any cell for its project and skill.")
        st.plotly_chart(heatmap_figure(current, instance), use_container_width=True, key="schedule_heatmap")
        st.caption("Light gray = available but unassigned; darker gray = vacation. "
                   "Hover over cells for the full project and qualification.")

        assignments = pd.DataFrame(current["assignments"])
        if not assignments.empty:
            employee_choices = ["All employees"] + employees
            worker = st.selectbox("Filter employee", employee_choices)
            shown = assignments if worker == "All employees" else assignments[
                assignments["employee_name"] == worker
            ]
            st.dataframe(
                shown[["day", "employee_name", "project_name", "qualification"]]
                .sort_values(["day", "employee_name"])
                .rename(columns={"day": "Day", "employee_name": "Employee",
                                 "project_name": "Project", "qualification": "Skill"}),
                use_container_width=True, hide_index=True,
            )
            st.download_button(
                "Download assignments (CSV)", data=shown.to_csv(index=False).encode("utf-8"),
                file_name=f"compuoti_{selected_label.lower()}_assignments.csv", mime="text/csv",
            )
        else:
            st.info("This portfolio contains no employee assignments.")

        usage = employee_utilization(current, instance)
        if not usage.empty:
            section_intro("Employee utilization", "Booked days divided by available working days after leave.")
            fig = go.Figure(go.Bar(
                x=usage["Employee"], y=usage["Utilization %"],
                marker_color=TEAL, customdata=usage[["Assigned days", "Available days"]].to_numpy(),
                hovertemplate="%{x}<br>%{customdata[0]} / %{customdata[1]} days<br>"
                              "Utilization: %{y:.1f}%<extra></extra>",
            ))
            fig.update_layout(
                height=320, template="plotly_white", margin={"l": 5, "r": 8, "t": 15, "b": 10},
                yaxis={"title": "% of available days", "range": [0, 105]},
                xaxis_title="Employee", font={"color": NAVY},
            )
            st.plotly_chart(fig, use_container_width=True, key="schedule_utilization")

    with tab_projects:
        section_intro(f"Portfolio decision · {selected_label}",
                      "Selected projects earn their gain; late delivery incurs penalties.")
        gross_known = project_df["Gross gain"].notna().any()
        money_columns = st.columns(3)
        if gross_known:
            gross = float(project_df["Gross gain"].fillna(0).sum())
            penalties = float(project_df["Late penalty"].fillna(0).sum())
            money_columns[0].metric("Gross selected gain", f"{gross:,.2f}")
            money_columns[1].metric("Late penalties", f"{penalties:,.2f}")
            money_columns[2].metric("Net gain", f"{values['financial']:,.2f}")
        else:
            st.info("Original instance not found; project gains and penalties cannot be itemized. "
                    "Saved net gain is still available.")

        selected_view = project_df.copy()
        selected_view["Completed"] = selected_view["Completed"].astype("Int64")
        st.dataframe(selected_view, use_container_width=True, hide_index=True)

        left, right = st.columns([1.5, 1], gap="large")
        with left:
            section_intro("Deadline vs. finish", "Red completion bars identify late deliveries.")
            if project_df["Selected"].any():
                st.plotly_chart(completion_figure(project_df), use_container_width=True, key="portfolio_deadline_comparison")
            else:
                st.info("No selected projects in this portfolio.")
        with right:
            section_intro("Portfolio breakdown", "How many projects were executed or skipped.")
            status_counts = project_df["Status"].value_counts()
            for status in ["On time", "Late", "Rejected"]:
                st.metric(status, int(status_counts.get(status, 0)))

        st.download_button(
            "Download selected solution (JSON)",
            data=json.dumps(current, indent=2, ensure_ascii=False).encode("utf-8"),
            file_name=f"compuoti_{selected_label.lower()}_solution.json",
            mime="application/json",
        )

    with tab_diagnostics:
        section_intro("ε-constraint search", "Solver outcomes over the sampled constraint grid.")
        attempted = int(data.get("attempted_combinations", 0))
        successes = int(data.get("successful_combinations", 0))
        infeasible = int(data.get("infeasible_combinations", 0))
        incomplete = int(data.get("incomplete_combinations", 0))
        chart = go.Figure(go.Bar(
            x=["Solved", "Infeasible", "Incomplete"],
            y=[successes, infeasible, incomplete],
            marker_color=[TEAL, GRAY, AMBER], text=[successes, infeasible, incomplete],
            textposition="outside",
        ))
        chart.update_layout(
            template="plotly_white", height=315, margin={"l": 10, "r": 10, "t": 30, "b": 15},
            yaxis_title="Grid combinations", font={"color": NAVY},
        )
        st.plotly_chart(chart, use_container_width=True, key="search_diagnostics")
        diagnostics = st.columns(4)
        diagnostics[0].metric("Attempted", attempted)
        diagnostics[1].metric("Gurobi optimizations", data.get("number_of_gurobi_optimizations", "—"))
        diagnostics[2].metric("Candidate schedules", data.get("candidate_count", "—"))
        diagnostics[3].metric("Frontier vectors", len(solutions))
        st.caption("An infeasible ε combination means those simultaneous limits could not be met; "
                   "it does not imply the input dataset is invalid.")
        epsilon_grid = data.get("epsilon_grid", {})
        if epsilon_grid:
            with st.expander("Bounds explored"):
                st.json(epsilon_grid)
        attempts = data.get("attempts", [])
        if attempts:
            with st.expander(f"Individual solver attempts ({len(attempts)})"):
                at_rows = []
                for index, attempt in enumerate(attempts, 1):
                    bounds = attempt.get("epsilon_bounds", {})
                    at_rows.append({"Run": index, "Status": attempt.get("status", "?"),
                                    "Completion bound": bounds.get("completion"),
                                    "Relationships bound": bounds.get("relationships"),
                                    "Late-projects bound": bounds.get("late_projects"),
                                    "Optimizations": attempt.get("number_of_optimizations")})
                st.dataframe(pd.DataFrame(at_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.caption("CompuOpti · Saved multiobjective results viewer · "
               "No solver runs are performed inside the dashboard.")


if __name__ == "__main__":
    main()
