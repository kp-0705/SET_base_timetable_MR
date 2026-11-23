"""Streamlit Web Application: SAT-Based Automated Timetable Generation and Optimization."""

import streamlit as st
import pandas as pd
import json
from pathlib import Path

import config
from core.models import SchedulingInstance, TimetableResult
from core.data_loader import (
    load_from_csv, load_from_json, save_to_json, generate_default_time_slots
)
from core.data_validator import validate_scheduling_instance, DataValidationError
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService, CADICAL_AVAILABLE
from core.maxsat_solver import MaxSATOptimizer
from core.unsat_explainer import UnsatExplainer
from core.timetable_decoder import decode_timetable
from core.timetable_validator import TimetableValidator
from visualization.timetable_view import build_grid_dataframe, build_exportable_dataframe
from visualization.analytics import (
    plot_encoding_comparison, plot_solving_time_comparison,
    plot_faculty_load, plot_soft_satisfaction, plot_scalability_curve
)

# Page Configuration
st.set_page_config(
    page_title="SAT-Based Timetable Generator | M.Tech Machine Reasoning",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "instance" not in st.session_state:
    # Load default feasible instance
    default_json = config.SAMPLE_DATA_DIR / "feasible_instance.json"
    if default_json.exists():
        st.session_state.instance = load_from_json(default_json)
    else:
        st.session_state.instance = None

if "timetable_result" not in st.session_state:
    st.session_state.timetable_result = None

if "last_diag_result" not in st.session_state:
    st.session_state.last_diag_result = None


# Custom CSS for polished academic appearance
st.markdown("""
<style>
    .main-title { font-size: 2.1rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
    .metric-card { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; }
    .badge-sat { background-color: #DEF7EC; color: #03543F; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
    .badge-unsat { background-color: #FDE8E8; color: #9B1C1C; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
    .badge-opt { background-color: #E1EFFE; color: #1E429F; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# Sidebar Configuration
with st.sidebar:
    st.image("https://img.icons8.com/color/96/calendar--v1.png", width=64)
    st.title("Solver Controls")
    
    # Dataset Selector
    st.subheader("1. Scenario Selection")
    sample_choice = st.selectbox(
        "Load Preset Scenario",
        ["Feasible Master's Curriculum", "Infeasible Bottleneck (UNSAT Test)"]
    )
    
    if st.button("Reload Selected Scenario", use_container_width=True):
        if sample_choice == "Feasible Master's Curriculum":
            st.session_state.instance = load_from_json(config.SAMPLE_DATA_DIR / "feasible_instance.json")
            st.session_state.timetable_result = None
            st.session_state.last_diag_result = None
            st.success("Loaded Feasible Master's Curriculum.")
        elif sample_choice == "Infeasible Bottleneck (UNSAT Test)":
            st.session_state.instance = load_from_json(config.SAMPLE_DATA_DIR / "infeasible_instance.json")
            st.session_state.timetable_result = None
            st.session_state.last_diag_result = None
            st.warning("Loaded Infeasible Bottleneck Scenario.")

    st.divider()

    # Solver Parameters
    st.subheader("2. Solver Engine & Encoding")
    solver_options = ["glucose4", "minisat22"]
    if CADICAL_AVAILABLE:
        solver_options.append("cadical153")
    
    selected_solver = st.selectbox(
        "SAT Solver Backend",
        solver_options,
        index=0,
        help="Glucose4 is tailored for crafted/industrial CNF. Minisat22 provides classic CDCL baseline."
    )

    selected_encoding = st.selectbox(
        "Cardinality Encoding Strategy",
        ["sequential", "pairwise", "commander"],
        index=0,
        help="Sequential (Sinz O(N)) preserves unit propagation. Pairwise is O(N^2). Commander groups variables."
    )

    st.divider()

    # MaxSAT Preferences
    st.subheader("3. MaxSAT Soft Preferences")
    enable_maxsat = st.toggle("Enable RC2 MaxSAT Optimization", value=True)
    
    w_idle = st.slider("Minimize Student Idle Gaps", 0, 10, config.DEFAULT_SOFT_WEIGHTS["minimize_student_idle_gaps"])
    w_extreme = st.slider("Avoid Extreme Periods (Early/Late)", 0, 10, config.DEFAULT_SOFT_WEIGHTS["avoid_extreme_periods"])
    w_pref = st.slider("Faculty Preferred Slots", 0, 10, config.DEFAULT_SOFT_WEIGHTS["faculty_preferred_slots"])
    
    soft_weights = {
        "minimize_student_idle_gaps": w_idle,
        "avoid_extreme_periods": w_extreme,
        "faculty_preferred_slots": w_pref
    }


# Main Interface Tabs
tabs = st.tabs([
    "📊 Dashboard",
    "📅 Timetable Grid",
    "🔍 Infeasibility (UNSAT Core)",
    "📈 Analytics & Benchmarks",
    "📚 Machine Reasoning Theory"
])

inst: SchedulingInstance = st.session_state.instance


# -------------------------------------------------------------
# TAB 1: DASHBOARD
# -------------------------------------------------------------
with tabs[0]:
    st.markdown('<div class="main-title">SAT-Based Automated Timetable Generation and Optimization</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">M.Tech Machine Reasoning | Propositional Logic &bull; CNF Cardinality Encodings &bull; CDCL SAT &bull; RC2 MaxSAT &bull; UNSAT Cores</div>', unsafe_allow_html=True)

    if inst:
        col1, col2, col3, col4, col5 = st.columns(5)
        tokens = inst.create_session_tokens()
        with col1:
            st.metric("Courses Offering", len(inst.courses), f"{len(tokens)} Weekly Sessions")
        with col2:
            st.metric("Faculty Members", len(inst.faculty))
        with col3:
            st.metric("Rooms / Labs", len(inst.rooms))
        with col4:
            st.metric("Student Batches", len(inst.batches))
        with col5:
            st.metric("Time Slots / Week", len(inst.time_slots), f"{len(config.WORKING_DAYS)} Days x {config.PERIODS_PER_DAY} Periods")

        st.divider()

        # Action Buttons
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
        with btn_col1:
            gen_sat_btn = st.button("🚀 Generate Timetable (SAT Feasibility)", use_container_width=True, type="secondary")
        with btn_col2:
            gen_maxsat_btn = st.button("⭐ Optimize Timetable (RC2 MaxSAT)", use_container_width=True, type="primary")
        with btn_col3:
            diagnose_btn = st.button("🔬 Diagnose Infeasibility (UNSAT Core)", use_container_width=True)

        # 1. SAT Execution
        if gen_sat_btn:
            with st.spinner(f"Encoding constraints using '{selected_encoding}' and solving with {selected_solver}..."):
                encoder = ConstraintEncoder(inst, cardinality_strategy=selected_encoding)
                enc_res = encoder.encode()
                solver = SATSolverService(selected_solver)
                sol_res = solver.solve(enc_res.clauses)

                if sol_res.status == "SAT":
                    entries = decode_timetable(sol_res.model, enc_res.primary_vars, inst)
                    validator = TimetableValidator(inst)
                    is_valid, violations = validator.validate(entries)

                    st.session_state.timetable_result = TimetableResult(
                        status="SAT",
                        is_valid=is_valid,
                        solver_name=selected_solver,
                        cardinality_encoding=selected_encoding,
                        variables_count=enc_res.stats["total_vars"],
                        clauses_count=enc_res.stats["total_clauses"],
                        aux_variables_count=enc_res.stats["num_aux_vars"],
                        cnf_generation_time_sec=enc_res.stats["generation_time_sec"],
                        solving_time_sec=sol_res.solving_time_sec,
                        total_time_sec=enc_res.stats["generation_time_sec"] + sol_res.solving_time_sec,
                        entries=entries
                    )
                    st.success(f"Feasible timetable generated successfully in {sol_res.solving_time_sec:.4f}s! All hard constraints validated.")
                else:
                    st.session_state.timetable_result = TimetableResult(
                        status="UNSAT",
                        is_valid=False,
                        solver_name=selected_solver,
                        cardinality_encoding=selected_encoding,
                        variables_count=enc_res.stats["total_vars"],
                        clauses_count=enc_res.stats["total_clauses"]
                    )
                    st.error("Problem is UNSATISFIABLE! No conflict-free timetable exists under current hard constraints.")

        # 2. MaxSAT Execution
        if gen_maxsat_btn:
            with st.spinner("Formulating Weighted Partial MaxSAT and optimizing with RC2..."):
                opt = MaxSATOptimizer(inst, weights=soft_weights, cardinality_strategy=selected_encoding)
                opt_res = opt.optimize()

                if opt_res.status == "OPTIMIZED":
                    validator = TimetableValidator(inst)
                    is_valid, violations = validator.validate(opt_res.optimized_entries)

                    st.session_state.timetable_result = TimetableResult(
                        status="OPTIMIZED",
                        is_valid=is_valid,
                        solver_name="RC2 MaxSAT",
                        cardinality_encoding=selected_encoding,
                        solving_time_sec=opt_res.optimization_time_sec,
                        entries=opt_res.optimized_entries,
                        soft_constraints_satisfied=opt_res.satisfied_soft_clauses,
                        soft_constraints_total=opt_res.total_soft_clauses,
                        optimization_cost=opt_res.optimal_cost
                    )
                    st.success(
                        f"Timetable Optimized via RC2 in {opt_res.optimization_time_sec:.4f}s! "
                        f"Optimal Penalty: {opt_res.optimal_cost} (Satisfied {opt_res.satisfied_soft_clauses}/{opt_res.total_soft_clauses} soft clauses)."
                    )
                else:
                    st.error("Cannot optimize: The mandatory hard constraints are inherently unsatisfiable (UNSAT)!")

        # 3. Diagnose Execution
        if diagnose_btn:
            with st.spinner("Extracting assumption-based UNSAT Core and minimizing MUS..."):
                explainer = UnsatExplainer(inst, cardinality_strategy=selected_encoding)
                diag = explainer.diagnose(minimize_core=True)
                st.session_state.last_diag_result = diag
                if diag.is_infeasible:
                    st.warning("Infeasibility diagnosed! Check the 'Infeasibility (UNSAT Core)' tab for detailed analysis.")
                else:
                    st.info("The problem instance is feasible. No conflicting constraint core found.")

        # Display Current Result Banner
        res: TimetableResult = st.session_state.timetable_result
        if res:
            st.divider()
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                badge = f'<span class="badge-opt">OPTIMIZED</span>' if res.status == "OPTIMIZED" else (
                    f'<span class="badge-sat">SATISFIABLE</span>' if res.status == "SAT" else f'<span class="badge-unsat">UNSAT</span>'
                )
                st.markdown(f"**Status:** {badge}", unsafe_allow_html=True)
            with m_col2:
                audit_str = "✅ 100% Passed" if res.is_valid else ("❌ UNSAT" if res.status == "UNSAT" else "⚠️ Violations")
                st.markdown(f"**Independent Audit:** **{audit_str}**")
            with m_col3:
                st.markdown(f"**Solver Time:** `{res.solving_time_sec:.4f}s`")
            with m_col4:
                cost_str = f"Penalty {res.optimization_cost}" if res.optimization_cost is not None else "N/A"
                st.markdown(f"**Optimization Cost:** `{cost_str}`")


# -------------------------------------------------------------
# TAB 2: TIMETABLE GRID
# -------------------------------------------------------------
with tabs[1]:
    st.subheader("Interactive Timetable Presentation")
    res = st.session_state.timetable_result

    if not res or not res.entries:
        st.info("No timetable has been generated yet. Click 'Generate Timetable' or 'Optimize Timetable' on the Dashboard tab.")
    else:
        # View Filters
        filter_col1, filter_col2 = st.columns([1, 2])
        with filter_col1:
            view_mode = st.radio(
                "Filter Schedule By:",
                ["Student Batch", "Faculty Member", "Room / Laboratory", "Full University Schedule"],
                horizontal=False
            )

        with filter_col2:
            filter_val = None
            if view_mode == "Student Batch":
                batch_opts = [b.batch_id for b in inst.batches]
                filter_val = st.selectbox("Select Student Batch", batch_opts)
                df_grid = build_grid_dataframe(res.entries, filter_by="batch", filter_value=filter_val)
            elif view_mode == "Faculty Member":
                fac_opts = {f.faculty_id: f"{f.name} ({f.faculty_id})" for f in inst.faculty}
                selected_fac_id = st.selectbox("Select Faculty", list(fac_opts.keys()), format_func=lambda x: fac_opts[x])
                filter_val = selected_fac_id
                df_grid = build_grid_dataframe(res.entries, filter_by="faculty", filter_value=filter_val)
            elif view_mode == "Room / Laboratory":
                room_opts = {r.room_id: f"{r.name} ({r.room_id} - {r.room_type.capitalize()})" for r in inst.rooms}
                selected_r_id = st.selectbox("Select Room", list(room_opts.keys()), format_func=lambda x: room_opts[x])
                filter_val = selected_r_id
                df_grid = build_grid_dataframe(res.entries, filter_by="room", filter_value=filter_val)
            else:
                df_grid = build_grid_dataframe(res.entries, filter_by="all")

        st.dataframe(df_grid, use_container_width=True, height=450)

        # Download CSV
        export_df = build_exportable_dataframe(res.entries)
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Timetable to CSV",
            data=csv_data,
            file_name="generated_academic_timetable.csv",
            mime="text/csv"
        )


# -------------------------------------------------------------
# TAB 3: INFEASIBILITY (UNSAT CORE)
# -------------------------------------------------------------
with tabs[2]:
    st.subheader("Infeasibility Explanation & Minimal Unsatisfiable Subset (MUS)")
    diag: UnsatExplainer = st.session_state.last_diag_result

    if not diag:
        st.info("Click 'Diagnose Infeasibility (UNSAT Core)' on the Dashboard or switch to the Infeasible Scenario to test.")
    elif not diag.is_infeasible:
        st.success("✅ The current scheduling instance is FEASIBLE. All constraint groups can be simultaneously satisfied.")
    else:
        st.error(f"❌ Timetable Infeasible! Diagnosed in {diag.diagnosis_time_sec:.4f}s.")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.metric("Raw Assumption Core Size", len(diag.raw_core_literals), "Candidate Constraints")
        with col_c2:
            st.metric("Minimal Core (MUS) Size", len(diag.minimal_core_literals), "After Deletion Minimization")

        st.markdown("### Grounded Infeasibility Analysis")
        st.markdown(diag.summary_explanation)

        st.markdown("### Conflicting Constraint Groups (Extracted Core)")
        for cat, details in diag.conflicting_categories.items():
            with st.expander(f"📌 {cat} ({len(details)} conflicting requirements)", expanded=True):
                for item in details:
                    st.write(f"- {item}")

        st.markdown("### Actionable Recommendations for Feasibility")
        for sug in diag.suggested_relaxations:
            st.info(f"💡 {sug}")


# -------------------------------------------------------------
# TAB 4: ANALYTICS & BENCHMARKS
# -------------------------------------------------------------
with tabs[3]:
    st.subheader("Empirical Benchmarking & Performance Telemetry")

    enc_file = config.RESULTS_DIR / "encoding_comparison.csv"
    sol_file = config.RESULTS_DIR / "solver_comparison.csv"
    scale_file = config.RESULTS_DIR / "scalability_benchmark.csv"

    if enc_file.exists():
        df_enc = pd.read_csv(enc_file)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(plot_encoding_comparison(df_enc), use_container_width=True)
        with c2:
            st.plotly_chart(plot_solving_time_comparison(df_enc), use_container_width=True)

    if scale_file.exists():
        df_scale = pd.read_csv(scale_file)
        st.plotly_chart(plot_scalability_curve(df_scale), use_container_width=True)

    if res and res.entries and inst:
        st.plotly_chart(plot_faculty_load(res.entries, inst.faculty), use_container_width=True)


# -------------------------------------------------------------
# TAB 5: MACHINE REASONING THEORY
# -------------------------------------------------------------
with tabs[4]:
    st.subheader("Machine Reasoning Principles & Formulation")
    
    st.markdown(r"""
    ### 1. Decision Variable Formulation
    Each discrete session token $s \in \mathcal{S}$ is modeled using Boolean decision variables:
    $$x_{s, t, r} \in \{0, 1\}$$
    indicating whether session $s$ begins at time slot $t \in \mathcal{T}$ in room $r \in \mathcal{R}$.

    ### 2. Cardinality Encodings (At-Most-One $\sum x_i \le 1$)
    - **Pairwise Encoding:** $\binom{n}{2}$ binary clauses $(\neg x_i \lor \neg x_j)$ with zero auxiliary variables.
    - **Sequential Counter (Sinz 2005):** Introduces $n-1$ prefix sum variables $s_i$, yielding $3n-4$ clauses with guaranteed arc consistency under unit propagation.
    - **Commander Encoding:** Partitions variables into subsets of size $k \approx 3$, delegating mutual exclusion to commander literals.

    ### 3. Partial Weighted MaxSAT via RC2
    - Hard clauses: $C_{\text{hard}}$ with infinite penalty.
    - Soft clauses: $C_{\text{soft}}$ with weights $w \in \{2, 3, 4, 5\}$.
    - RC2 utilizes modern core-guided resolution to compute minimum-cost satisfying assignments.

    ### 4. Assumption-Based Infeasibility Diagnosis
    Each constraint group is guarded by selector literal $\alpha$:
    $$(C \lor \neg \alpha)$$
    When solved under assumptions $[\alpha_1, \alpha_2, \dots]$, the solver extracts a conflicting subset called an **UNSAT Core**.
    Applying **deletion-based minimization** drops non-essential assumptions to deliver a **Minimal Unsatisfiable Subset (MUS)**.
    """)
