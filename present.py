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
	st.session_state.events = []
	st.session_state.book_value = initial_asset
	st.session_state.salvage_rate = salvage_rate
	st.session_state.current_salvage = initial_asset * salvage_rate
	st.session_state.method = params["method"]
	st.session_state.cap_ratio = float(params["cap_ratio"])
	st.session_state.impair_ratio = float(params["impair_ratio"])
	st.session_state.upgrade_pending = False
	st.session_state.upgrade_pending_delta = 0.0
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


def advance_one_month():
	if st.session_state.month_idx >= st.session_state.total_months:
		st.session_state.running = False
		st.session_state.page = "end"
		return

	# During upgrade request period, timeline still advances but depreciation is set to zero.
	if st.session_state.upgrade_pending:
		st.session_state.history.append(0.0)
		st.session_state.month_idx += 1
		if st.session_state.month_idx >= st.session_state.total_months:
			st.session_state.running = False
			st.session_state.page = "end"
		return

	if not st.session_state.current_schedule:
		recalc_schedule()

	dep = st.session_state.current_schedule[0] if st.session_state.current_schedule else 0.0
	dep = min(dep, max(st.session_state.book_value - st.session_state.current_salvage, 0.0))

	st.session_state.history.append(dep)
	st.session_state.book_value -= dep
	st.session_state.month_idx += 1
	st.session_state.current_schedule = st.session_state.current_schedule[1:]

	if st.session_state.month_idx >= st.session_state.total_months:
		st.session_state.running = False
		st.session_state.page = "end"


def render_chart():
	months = list(range(1, len(st.session_state.history) + 1))
	values = st.session_state.history if st.session_state.history else [0.0]
	x_values = months if months else [1]

	fig = go.Figure()
	fig.add_trace(
		go.Scatter(
			x=x_values,
			y=values,
			mode="lines",
			line={"shape": "spline", "smoothing": 1.1, "width": 4, "color": "#ff8c42"},
			name="Monthly Depreciation",
		)
	)

	if st.session_state.events and months:
		for event in st.session_state.events:
			month = event["month"]
			if month <= 0 or month > len(values):
				continue
			fig.add_trace(
				go.Scatter(
					x=[month],
					y=[values[month - 1]],
					mode="markers+text",
					marker={"size": 10, "color": event["color"]},
					text=[event["label"]],
					textposition="top center",
					name=event["label"],
				)
			)

	fig.update_layout(
		margin={"l": 24, "r": 20, "t": 20, "b": 30},
		paper_bgcolor="#121212",
		plot_bgcolor="#191919",
		xaxis={"title": "Month", "gridcolor": "#2a2a2a", "color": "#d6d6d6"},
		yaxis={"title": "Depreciation", "gridcolor": "#2a2a2a", "color": "#d6d6d6"},
		legend={"orientation": "h", "y": 1.12, "x": 0},
		height=360,
	)
	st.plotly_chart(fig, use_container_width=True)


st.markdown(
	"""
	<style>
	.title-wrap {
		background: linear-gradient(135deg, #f9f4eb 0%, #efe5d8 100%);
		border: 1px solid #d9c8ae;
		border-radius: 16px;
		padding: 18px 22px;
		margin-bottom: 12px;
		font-family: 'Avenir Next', 'PingFang SC', sans-serif;
	}
	.handheld {
		background: linear-gradient(160deg, #f3ede4 0%, #e7dccb 100%);
		border: 2px solid #bfa98b;
		border-radius: 24px;
		padding: 18px;
		box-shadow: 0 14px 36px rgba(72, 44, 20, 0.20);
	}
	.mini-note {
		color: #7f6b55;
		font-size: 0.95rem;
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
	st.info("Press enter to launch the handheld simulator. Use three buttons to create business events and track the accounting response.")
	if st.button("Enter Simulator", type="primary"):
		init_state(params)
		st.rerun()

elif st.session_state.page == "end":
	st.markdown(
		"""
		<div class="title-wrap">
			<h2 style="margin:0; color:#2f2418;">Simulation Completed</h2>
			<p style="margin-top:8px; color:#59452f;">You have reached the end of useful life. Compare event moments with the depreciation curve to narrate business-finance linkage.</p>
		</div>
		""",
		unsafe_allow_html=True,
	)
	total_dep = sum(st.session_state.history)
	col_a, col_b, col_c = st.columns(3)
	col_a.metric("Months Simulated", st.session_state.month_idx)
	col_b.metric("Total Depreciation", f"{total_dep:,.0f}")
	col_c.metric("Ending Book Value", f"{st.session_state.book_value:,.0f}")
	render_chart()
	if st.button("Play Again", type="primary"):
		init_state(params)
		st.rerun()

else:
	st.markdown(
		"""
		<div class="title-wrap">
			<h2 style="margin:0; color:#2f2418;">Business Event x Finance Data Pattern</h2>
			<p style="margin-top:6px; color:#59452f;">Left: Capitalization | Middle: Start/Stop | Right: Impairment</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

	st.markdown('<div class="handheld">', unsafe_allow_html=True)
	render_chart()
	meta_1, meta_2, meta_3, meta_4 = st.columns(4)
	meta_1.metric("Method", st.session_state.method)
	meta_2.metric("Current Month", f"{st.session_state.month_idx}/{st.session_state.total_months}")
	meta_3.metric("Book Value", f"{st.session_state.book_value:,.0f}")
	status_label = "Pending" if st.session_state.upgrade_pending else "Normal"
	meta_4.metric("Status", status_label)

	left, mid, right = st.columns([1, 1, 1])
	with left:
		left_label = "Upgrade Acceptance" if st.session_state.upgrade_pending else "Upgrade Request"
		if st.button(left_label, use_container_width=True):
			if st.session_state.upgrade_pending:
				apply_upgrade_acceptance()
			else:
				apply_upgrade_request()
			st.rerun()
	with mid:
		toggle_label = "Stop Depreciation" if st.session_state.running else "Start Depreciation"
		if st.button(toggle_label, type="primary", use_container_width=True):
			st.session_state.running = not st.session_state.running
			st.rerun()
	with right:
		if st.button("Impairment", use_container_width=True, disabled=st.session_state.upgrade_pending):
			apply_impairment()
			st.rerun()

	if st.session_state.upgrade_pending:
		st.caption("Upgrade request in progress: timeline continues and monthly depreciation is 0 until acceptance.")
	else:
		st.caption("Business actions re-base remaining depreciation path using current carrying amount and selected method.")
	st.markdown("</div>", unsafe_allow_html=True)

	if st.session_state.running:
		advance_one_month()
		time.sleep(0.35)
		st.rerun()
