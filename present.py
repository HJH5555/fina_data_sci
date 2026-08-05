import random
import time

import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Depreciation Game", layout="wide")


def monthly_schedule(method, book_value, salvage_value, remaining_months):
	if remaining_months <= 0:
		return []

	depreciable = max(book_value - salvage_value, 0.0)
	if depreciable <= 0:
		return [0.0] * remaining_months

	schedule = []
	if method == "Straight-Line":
		per_month = depreciable / remaining_months
		schedule = [per_month] * remaining_months

	elif method == "Double-Declining":
		months_in_year = 12
		annual_life = max(remaining_months / months_in_year, 1 / months_in_year)
		annual_rate = 2 / annual_life
		current_book = book_value

		for i in range(remaining_months):
			months_left = remaining_months - i
			ddb_amount = current_book * annual_rate / months_in_year
			straight_line_floor = max(current_book - salvage_value, 0.0) / months_left
			dep = min(max(ddb_amount, straight_line_floor), max(current_book - salvage_value, 0.0))
			schedule.append(dep)
			current_book -= dep

	else:  # SYD (Sum-of-the-Years'-Digits)
		n = remaining_months
		denominator = n * (n + 1) / 2
		for i in range(remaining_months):
			remaining_weight = n - i
			dep = depreciable * remaining_weight / denominator
			schedule.append(dep)

	return schedule


def init_state(params):
	initial_asset = float(params["initial_asset"])
	salvage_rate = float(params["salvage_rate"])
	useful_years = int(params["useful_years"])

	st.session_state.page = "game"
	st.session_state.running = False
	st.session_state.month_idx = 0
	st.session_state.total_months = useful_years * 12
	st.session_state.history = []
	st.session_state.history_company_a = []
	st.session_state.history_company_b = []
	st.session_state.events = []
	st.session_state.book_value = initial_asset
	st.session_state.salvage_rate = salvage_rate
	st.session_state.current_salvage = initial_asset * salvage_rate
	st.session_state.method = params["method"]
	st.session_state.cap_ratio = float(params["cap_ratio"])
	st.session_state.impair_ratio = float(params["impair_ratio"])
	st.session_state.upgrade_pending = False
	st.session_state.upgrade_pending_delta = 0.0
	st.session_state.current_owner = "A"
	st.session_state.current_schedule = monthly_schedule(
		method=st.session_state.method,
		book_value=st.session_state.book_value,
		salvage_value=st.session_state.current_salvage,
		remaining_months=st.session_state.total_months,
	)
	st.session_state.params_signature = tuple(params.items())


def recalc_schedule():
	remaining = st.session_state.total_months - st.session_state.month_idx
	st.session_state.current_salvage = st.session_state.book_value * st.session_state.salvage_rate
	st.session_state.current_schedule = monthly_schedule(
		method=st.session_state.method,
		book_value=st.session_state.book_value,
		salvage_value=st.session_state.current_salvage,
		remaining_months=remaining,
	)


def apply_upgrade_request():
	if st.session_state.month_idx >= st.session_state.total_months:
		return
	if st.session_state.upgrade_pending:
		return

	jitter = random.uniform(0.9, 1.1)
	delta = st.session_state.book_value * st.session_state.cap_ratio * jitter
	st.session_state.upgrade_pending = True
	st.session_state.upgrade_pending_delta = delta
	st.session_state.events.append(
		{
			"month": st.session_state.month_idx,
			"label": f"Upgrade Request +{delta:,.0f}",
			"color": "#1c9a6d",
		}
	)


def apply_upgrade_acceptance():
	if st.session_state.month_idx >= st.session_state.total_months:
		return
	if not st.session_state.upgrade_pending:
		return

	delta = st.session_state.upgrade_pending_delta
	st.session_state.book_value += delta
	st.session_state.events.append(
		{
			"month": st.session_state.month_idx,
			"label": f"Upgrade Accepted +{delta:,.0f}",
			"color": "#0c7f58",
		}
	)
	st.session_state.upgrade_pending = False
	st.session_state.upgrade_pending_delta = 0.0
	recalc_schedule()


def apply_impairment():
	if st.session_state.month_idx >= st.session_state.total_months:
		return
	if st.session_state.upgrade_pending:
		return

	jitter = random.uniform(0.9, 1.1)
	delta = st.session_state.book_value * st.session_state.impair_ratio * jitter
	st.session_state.book_value = max(st.session_state.book_value - delta, 0.0)
	st.session_state.events.append(
		{
			"month": st.session_state.month_idx,
			"label": f"Impairment -{delta:,.0f}",
			"color": "#bb3f3f",
		}
	)
	recalc_schedule()


def apply_transfer():
	if st.session_state.month_idx >= st.session_state.total_months:
		return
	if st.session_state.upgrade_pending:
		return

	new_owner = "B" if st.session_state.current_owner == "A" else "A"
	st.session_state.current_owner = new_owner
	recalc_schedule()
	st.session_state.events.append(
		{
			"month": st.session_state.month_idx,
			"label": f"→ Co.{new_owner}  {st.session_state.book_value:,.0f}",
			"color": "#6a4c93",
		}
	)


def advance_one_month():
	if st.session_state.month_idx >= st.session_state.total_months:
		st.session_state.running = False
		st.session_state.page = "end"
		return

	# During upgrade request period both companies record 0
	if st.session_state.upgrade_pending:
		st.session_state.history_company_a.append(0.0)
		st.session_state.history_company_b.append(0.0)
		st.session_state.month_idx += 1
		if st.session_state.month_idx >= st.session_state.total_months:
			st.session_state.running = False
			st.session_state.page = "end"
		return

	if not st.session_state.current_schedule:
		recalc_schedule()

	dep = st.session_state.current_schedule[0] if st.session_state.current_schedule else 0.0
	dep = min(dep, max(st.session_state.book_value - st.session_state.current_salvage, 0.0))

	if st.session_state.current_owner == "A":
		st.session_state.history_company_a.append(dep)
		st.session_state.history_company_b.append(0.0)
	else:
		st.session_state.history_company_a.append(0.0)
		st.session_state.history_company_b.append(dep)

	st.session_state.book_value -= dep
	st.session_state.current_schedule = st.session_state.current_schedule[1:]
	st.session_state.month_idx += 1
	if st.session_state.month_idx >= st.session_state.total_months:
		st.session_state.running = False
		st.session_state.page = "end"


def render_chart_company(company):
	if company == "A":
		history = list(st.session_state.history_company_a) if st.session_state.history_company_a else [0.0]
		label = "Company A"
		color = "#ff8c42"
	else:
		history = list(st.session_state.history_company_b) if st.session_state.history_company_b else [0.0] * max(st.session_state.month_idx, 1)
		label = "Company B"
		color = "#6a4c93"

	months = list(range(1, len(history) + 1))

	fig = go.Figure()
	fig.add_trace(
		go.Scatter(
			x=months,
			y=history,
			mode="lines",
			line={"shape": "spline", "smoothing": 1.1, "width": 4, "color": color},
			name=f"{label} Depreciation",
			hoverinfo="skip",
		)
	)

	ev_x, ev_y, ev_text, ev_colors = [], [], [], []
	for event in st.session_state.events:
		month = event["month"]
		if month <= 0 or month > len(history):
			continue
		ev_x.append(month)
		ev_y.append(history[month - 1])
		ev_text.append(event["label"])
		ev_colors.append(event["color"])

	if ev_x:
		fig.add_trace(
			go.Scatter(
				x=ev_x,
				y=ev_y,
				mode="markers+text",
				marker={"size": 11, "color": ev_colors, "line": {"color": "#fffaf0", "width": 2}},
				text=ev_text,
				textposition="top center",
				textfont={"color": ev_colors, "size": 11, "family": "Avenir Next, PingFang SC, sans-serif"},
				showlegend=False,
				hoverinfo="skip",
			)
		)

	fig.update_layout(
		title={"text": label, "font": {"color": "#5b4a36", "size": 14, "family": "Avenir Next, PingFang SC, sans-serif"}, "x": 0.5},
		margin={"l": 24, "r": 20, "t": 44, "b": 30},
		paper_bgcolor="#fdfaf3",
		plot_bgcolor="#fffaf0",
		xaxis={"title": "Month", "gridcolor": "#ece1c8", "color": "#7f6b55", "linecolor": "#d9c8ae", "zerolinecolor": "#e8dfca"},
		yaxis={"title": "Depreciation", "gridcolor": "#ece1c8", "color": "#7f6b55", "linecolor": "#d9c8ae", "zerolinecolor": "#e8dfca"},
		font={"family": "Avenir Next, PingFang SC, sans-serif", "color": "#5b4a36"},
		showlegend=False,
		height=280,
		uirevision="static",
	)
	st.plotly_chart(fig, use_container_width=True, key=f"chart_{company}", config={"displayModeBar": False})


st.markdown(
	"""
	<style>
	html, body, [data-testid="stAppViewContainer"] {
		background: linear-gradient(180deg, #fdfaf3 0%, #f6efe2 100%);
		font-family: 'Avenir Next', 'PingFang SC', 'Helvetica Neue', sans-serif;
	}
	.title-wrap {
		background: linear-gradient(135deg, #f9f4eb 0%, #efe5d8 100%);
		border: 1px solid #d9c8ae;
		border-radius: 16px;
		padding: 18px 22px;
		margin-bottom: 14px;
	}
	.mini-note { color: #7f6b55; font-size: 0.95rem; }
	.status-banner {
		background: #fdf3dc;
		border: 1px solid #e6c98a;
		border-left: 4px solid #c2a878;
		border-radius: 10px;
		padding: 10px 14px;
		color: #6a4f25;
		margin-top: 10px;
		font-size: 0.95rem;
	}
	.muted-caption {
		color: #8b7860;
		font-size: 0.9rem;
		margin-top: 8px;
	}
	[data-testid="stSidebar"] { background: #f6efe2; }
	[data-testid="stSidebar"] *,
	[data-testid="stSidebar"] label,
	[data-testid="stSidebar"] h1,
	[data-testid="stSidebar"] h2,
	[data-testid="stSidebar"] h3,
	[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
	[data-testid="stSidebar"] [data-baseweb="select"] div { color: #3d2f1f; }
	[data-testid="stSidebar"] input,
	[data-testid="stSidebar"] [data-baseweb="input"] input { color: #3d2f1f !important; }
	[data-testid="stAppViewContainer"] .stMarkdown,
	[data-testid="stAppViewContainer"] .stMarkdown p,
	[data-testid="stAppViewContainer"] .stMarkdown li,
	[data-testid="stAppViewContainer"] h1,
	[data-testid="stAppViewContainer"] h2,
	[data-testid="stAppViewContainer"] h3 { color: #3d2f1f; }
	[data-testid="stMetric"] {
		background: #fdfaf3;
		border: 1px solid #e8dfca;
		border-radius: 12px;
		padding: 10px 14px;
	}
	[data-testid="stMetricLabel"] p { color: #8b7860; }
	[data-testid="stMetricValue"] { color: #3d2f1f; }
	.stButton > button {
		border-radius: 12px;
		border: 1px solid #d9c8ae;
		background: #fdfaf3;
		color: #3d2f1f;
		font-weight: 500;
		transition: background 120ms ease, border-color 120ms ease;
	}
	.stButton > button:hover:not(:disabled) {
		background: #f4ead8;
		border-color: #c2a878;
	}
	.stButton > button:disabled { opacity: 0.45; }
	.stButton > button[kind="primary"] {
		background: linear-gradient(135deg, #c2a878 0%, #a78a5b 100%);
		border-color: #a78a5b;
		color: #fff;
	}
	.stButton > button[kind="primary"]:hover:not(:disabled) {
		background: linear-gradient(135deg, #b89a66 0%, #8f7647 100%);
	}
	</style>
	""",
	unsafe_allow_html=True,
)

with st.sidebar:
	st.header("Scenario Setup")
	initial_asset = st.number_input("Initial Asset Value", min_value=10000.0, value=1200000.0, step=10000.0)
	useful_years = st.slider("Useful Life (Years)", min_value=2, max_value=12, value=6)
	salvage_rate = st.slider("Residual Rate", min_value=0.0, max_value=0.20, value=0.05, step=0.01)
	method = st.selectbox("Depreciation Method", ["Straight-Line", "Double-Declining", "SYD"])
	cap_ratio = st.slider("Capitalization Ratio", min_value=0.05, max_value=0.40, value=0.18, step=0.01)
	impair_ratio = st.slider("Impairment Ratio", min_value=0.05, max_value=0.40, value=0.12, step=0.01)

	params = {
		"initial_asset": initial_asset,
		"useful_years": useful_years,
		"salvage_rate": salvage_rate,
		"method": method,
		"cap_ratio": cap_ratio,
		"impair_ratio": impair_ratio,
	}

	if st.button("Reset Scenario", use_container_width=True):
		init_state(params)
		st.rerun()

if "page" not in st.session_state:
	st.session_state.page = "start"

# Compatibility guard for older session state snapshots after schema changes.
required_keys = [
	"running",
	"month_idx",
	"total_months",
	"history_company_a",
	"history_company_b",
	"book_value",
	"current_owner",
	"current_schedule",
	"upgrade_pending",
	"events",
]
if st.session_state.page != "start" and any(key not in st.session_state for key in required_keys):
	init_state(params)
	st.rerun()

if st.session_state.page == "start":
	st.markdown(
		"""
		<div class="title-wrap">
			<h1 style="margin:0 0 8px 0; color:#2f2418;">02 Financial Data Game - Depreciation Dynamics</h1>
			<p style="margin:0; color:#59452f;">Observe how business events reshape monthly depreciation trajectories.</p>
		</div>
		""",
		unsafe_allow_html=True,
	)
	st.info("Click **Enter Simulator** to start. Use the four action buttons to trigger business events and watch the depreciation curve respond.")
	if st.button("Enter Simulator", type="primary"):
		init_state(params)
		st.rerun()

elif st.session_state.page == "end":
	st.markdown(
		"""
		<div class="title-wrap">
			<h2 style="margin:0; color:#2f2418;">Simulation Completed</h2>
			<p style="margin-top:8px; color:#59452f;">Asset has reached end of useful life. Compare each event with the curve to see how business decisions shape financial outcomes.</p>
		</div>
		""",
		unsafe_allow_html=True,
	)
	total_dep_a = sum(st.session_state.history_company_a)
	total_dep_b = sum(st.session_state.history_company_b)
	total_dep = total_dep_a + total_dep_b
	col_a, col_b, col_c, col_d = st.columns(4)
	col_a.metric("Months Simulated", st.session_state.month_idx)
	col_b.metric("Company A Total Dep", f"{total_dep_a:,.0f}")
	col_c.metric("Company B Total Dep", f"{total_dep_b:,.0f}")
	col_d.metric("Combined Total Dep", f"{total_dep:,.0f}")
	render_chart_company("A")
	render_chart_company("B")
	if st.button("Play Again", type="primary"):
		init_state(params)
		st.rerun()

else:
	st.markdown(
		"""
		<div class="title-wrap">
			<h2 style="margin:0; color:#2f2418;">Business Event x Finance Data Pattern</h2>
			<p style="margin-top:6px; color:#59452f;">Capitalize · Run/Pause · Impair · Transfer between companies</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

	render_chart_company("A")
	render_chart_company("B")
	meta_1, meta_2, meta_3, meta_4 = st.columns(4)
	meta_1.metric("Method", st.session_state.method)
	meta_2.metric("Current Month", f"{st.session_state.month_idx}/{st.session_state.total_months}")
	
	display_value = f"{st.session_state.book_value:,.0f}"
	meta_3.metric("Book Value", display_value)

	if st.session_state.upgrade_pending:
		status_label = "Upgrade Pending"
	else:
		status_label = f"Owner: Co.{st.session_state.current_owner}"
	meta_4.metric("Status", status_label)

	btn1, btn2, btn3, btn4 = st.columns([1, 1, 1, 1])
	with btn1:
		left_label = "Upgrade Acceptance" if st.session_state.upgrade_pending else "Upgrade Request"
		left_help = (
			"Confirm last month's upgrade. The capitalized amount is added to book value and depreciation resumes."
			if st.session_state.upgrade_pending
			else "Capitalize an upgrade. Depreciation pauses for this month and the next, until you accept."
		)
		if st.button(left_label, use_container_width=True, help=left_help):
			if st.session_state.upgrade_pending:
				apply_upgrade_acceptance()
			else:
				apply_upgrade_request()
			st.rerun()
	with btn2:
		toggle_label = "Pause" if st.session_state.running else "Run"
		toggle_help = "Pause the timeline." if st.session_state.running else "Advance one month every 0.35 seconds."
		if st.button(toggle_label, type="primary", use_container_width=True, help=toggle_help):
			st.session_state.running = not st.session_state.running
			st.rerun()
	with btn3:
		if st.button(
			"Impairment",
			use_container_width=True,
			disabled=st.session_state.upgrade_pending,
			help="Recognize an impairment loss. Book value drops and remaining depreciation is rebalanced.",
		):
			apply_impairment()
			st.rerun()
	with btn4:
		next_owner = "B" if st.session_state.current_owner == "A" else "A"
		transfer_label = f"Transfer → Co.{next_owner}"
		if st.button(
			transfer_label,
			use_container_width=True,
			disabled=st.session_state.upgrade_pending,
			help=f"Move the asset to Company {next_owner}. Net book value carries forward; the curve switches lines.",
		):
			apply_transfer()
			st.rerun()

	if st.session_state.upgrade_pending:
		st.markdown(
			f"<div class='status-banner'>Upgrade pending — depreciation is paused this month. Click <b>Upgrade Acceptance</b> next month to capitalize <b>+{st.session_state.upgrade_pending_delta:,.0f}</b>.</div>",
			unsafe_allow_html=True,
		)
	else:
		st.markdown(
			"<div class='muted-caption'>Each business action re-bases the remaining depreciation path using current book value and the selected method.</div>",
			unsafe_allow_html=True,
		)

	if st.session_state.running:
		advance_one_month()
		time.sleep(0.35)
		st.rerun()
