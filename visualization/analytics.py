"""Plotly and Matplotlib charting utilities for analytics and benchmarking."""

from typing import List, Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.models import TimetableEntry, Faculty
from config import WORKING_DAYS


def plot_encoding_comparison(comparison_df: pd.DataFrame) -> go.Figure:
    """Creates a multi-bar chart comparing Variables, Clauses, and Solve Time across encodings."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=comparison_df["Strategy"],
        y=comparison_df["Total Clauses"],
        name="Total Clauses",
        marker_color="#EF553B"
    ))

    fig.add_trace(go.Bar(
        x=comparison_df["Strategy"],
        y=comparison_df["Total Variables"],
        name="Total Variables",
        marker_color="#636EFA"
    ))

    fig.update_layout(
        title="CNF Size by Cardinality Encoding Strategy",
        xaxis_title="Encoding Strategy",
        yaxis_title="Count (Log Scale)",
        yaxis_type="log",
        barmode="group",
        template="plotly_white"
    )
    return fig


def plot_solving_time_comparison(comparison_df: pd.DataFrame) -> go.Figure:
    """Creates bar chart for solving times across encodings."""
    fig = px.bar(
        comparison_df,
        x="Strategy",
        y="Solving Time (ms)",
        color="Strategy",
        title="SAT Solving Latency by Cardinality Encoding Strategy",
        text_auto=".2f",
        template="plotly_white"
    )
    fig.update_layout(showlegend=False)
    return fig


def plot_faculty_load(entries: List[TimetableEntry], faculty_list: List[Faculty]) -> go.Figure:
    """Visualizes weekly distribution of faculty teaching hours."""
    fac_names = {f.faculty_id: f.name for f in faculty_list}
    data: List[Dict[str, Any]] = []

    for e in entries:
        for _ in range(e.duration):
            data.append({
                "Faculty": fac_names.get(e.faculty_id, e.faculty_id),
                "Day": e.day,
                "Hours": 1
            })

    if not data:
        return go.Figure()

    df = pd.DataFrame(data)
    grouped = df.groupby(["Faculty", "Day"]).size().reset_index(name="Teaching Periods")

    fig = px.bar(
        grouped,
        x="Faculty",
        y="Teaching Periods",
        color="Day",
        title="Faculty Weekly Teaching Load Distribution",
        category_orders={"Day": WORKING_DAYS},
        template="plotly_white"
    )
    return fig


def plot_soft_satisfaction(breakdown: Dict[str, Dict[str, int]]) -> go.Figure:
    """Donut chart illustrating satisfaction percentage of soft constraints."""
    labels = []
    satisfied_vals = []
    violated_vals = []

    for rule_name, data in breakdown.items():
        clean_name = rule_name.replace("_", " ").title()
        labels.append(clean_name)
        satisfied_vals.append(data.get("satisfied", 0))
        violated_vals.append(data.get("violated", 0))

    fig = go.Figure(data=[
        go.Bar(name="Satisfied", x=labels, y=satisfied_vals, marker_color="#00CC96"),
        go.Bar(name="Violated (Penalty)", x=labels, y=violated_vals, marker_color="#AB63FA")
    ])

    fig.update_layout(
        title="Soft Constraint Satisfaction Breakdown",
        barmode="stack",
        yaxis_title="Clauses Evaluated",
        template="plotly_white"
    )
    return fig


def plot_scalability_curve(scalability_df: pd.DataFrame) -> go.Figure:
    """Plots solving time scaling against number of courses."""
    fig = px.line(
        scalability_df,
        x="Courses Count",
        y="Solve Time (s)",
        markers=True,
        title="SAT Scalability Curve (Course Count vs Solving Time)",
        template="plotly_white"
    )
    fig.update_traces(line=dict(width=3, color="#1f77b4"))
    return fig
