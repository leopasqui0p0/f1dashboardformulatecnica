import streamlit as st
import pandas as pd
import numpy as np
import scipy.signal as signal
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import fastf1
import fastf1.plotting
from fastf1.core import DataNotLoadedError
import os
import shutil
import io
import matplotlib.pyplot as plt
import base64
from datetime import datetime
from PIL import Image

# ==============================================================================
# WATERMARK & LOGO LOCALE
# ==============================================================================
LOGO_FILENAME = "logo.png"


def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return f"data:image/png;base64,{base64.b64encode(img_file.read()).decode()}"
    return "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/F1.svg/320px-F1.svg.png"


WATERMARK_URL = get_base64_image(LOGO_FILENAME)
LOGO_URL = WATERMARK_URL


# ==============================================================================
# BLOCCO PASSWORD
# ==============================================================================
def check_password():
    """Ritorna True se l'utente ha inserito la password corretta."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("<h1 style='text-align: center; color: #FF2800;'>F1 PITWALL PRO - ACCESSO RISERVATO</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Inserisci la password di sblocco:", type="password")

        # Sostituisci 'formula2026' con la password che preferisci!
        if pwd == "formula2026":
            st.session_state["password_correct"] = True
            st.rerun()
        elif pwd:
            st.error("Password errata. Riprova.")
        return False
    return True


if not check_password():
    st.stop()  # Blocca l'esecuzione di tutto il resto del codice se non c'è la password


# ==============================================================================
# ==============================================================================
# FUNZIONE PER ESPORTARE I DATAFRAME IN IMMAGINI (NIGHT MODE) CON AUTO-SCALING
# ==============================================================================
def create_image_from_df(df, title="Table"):
    """Converte un DataFrame Pandas in un'immagine PNG stilizzata in Night Mode senza sovrapposizioni"""
    df_clean = df.fillna("").astype(str)

    col_chars = [max(df_clean[col].map(len).max(), len(str(col))) + 2 for col in df_clean.columns]
    total_chars = sum(col_chars)

    col_widths = [c / total_chars for c in col_chars]

    fig_width = max(8, total_chars * 0.18)
    fig_height = max(3, len(df) * 0.6 + 2)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor('#111111')
    ax.axis('tight')
    ax.axis('off')

    header_color = '#FF2800'
    row_colors = ['#1a1a1a', '#222222']
    edge_color = '#333333'

    table = ax.table(cellText=df_clean.values,
                     colLabels=df_clean.columns,
                     colWidths=col_widths,
                     loc='center',
                     cellLoc='center')

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(edge_color)
        if row == 0:
            cell.set_facecolor(header_color)
            cell.set_text_props(weight='bold', color='white', family='sans-serif')
        else:
            cell.set_facecolor(row_colors[row % len(row_colors)])
            cell.set_text_props(color='#cccccc', family='monospace')

    plt.title(title, color='white', fontsize=18, fontweight='bold', family='sans-serif', pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor(), dpi=200)
    buf.seek(0)
    plt.close(fig)
    return buf


# ==============================================================================
# FUNZIONE PER GENERARE IL NOME DEL FILE IN BASE ALLA LOGICA RICHIESTA
# ==============================================================================
def generate_filename(year, event_name, is_test, test_number, day_str, plot_name, drivers_list):
    """
    Genera il nome del file es: BAH26_SPEED_LEC_VER oppure BAH26T01_D1_SPEED_LEC
    """
    short_year = str(year)[-2:]
    event_prefix = str(event_name)[:3].upper()

    if is_test:
        test_str = f"T{test_number:02d}"
        day_num = day_str.replace("Day ", "D")
        base_name = f"{event_prefix}{short_year}{test_str}_{day_num}"
    else:
        base_name = f"{event_prefix}{short_year}"

    drivers_str = "_".join(drivers_list) if drivers_list else "ALL"
    clean_plot_name = plot_name.replace(" ", "")

    return f"{base_name}_{clean_plot_name}_{drivers_str}.png"


# ==============================================================================
# 1. CONFIGURAZIONE E STILE
# ==============================================================================
st.set_page_config(
    page_title="F1 PITWALL PRO - 2026",
    layout="wide",
    page_icon="🏎️",
    initial_sidebar_state="expanded"
)

# Gestione Cache e Cartelle
CACHE_DIR = 'cache'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

if st.sidebar.button("🧹 Clear Cache & Reset", help="Clicca per eliminare download corrotti"):
    try:
        fastf1.Cache.clear_cache(CACHE_DIR)
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        os.makedirs(CACHE_DIR)
        st.cache_data.clear()
        st.cache_resource.clear()
        st.sidebar.success("Cache pulita! Ricarica i dati.")
    except Exception as e:
        st.sidebar.error(f"Errore cache: {e}")

fastf1.Cache.enable_cache(CACHE_DIR)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Roboto+Mono:wght@400;700&display=swap');
    .stApp { background-color: #000000; color: #ffffff; }
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    h1, h2, h3, h4, h5, .stMetricLabel { font-family: 'Anton', sans-serif !important; text-transform: uppercase; letter-spacing: 0.05em; color: #ffffff !important; }
    .stMarkdown p, .stDataFrame, div[data-testid="stMetricValue"], .stTable, label { font-family: 'Roboto Mono', monospace !important; color: #cccccc !important; }
    section[data-testid="stSidebar"] { background-color: #0f0f0f; border-right: 2px solid #FF2800; }
    div[data-baseweb="select"] > div { background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #333333 !important; }
    div[data-baseweb="popover"] > div { background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #333333 !important; }
    ul[role="listbox"] { background-color: #1a1a1a !important; }
    li[role="option"] { color: #ffffff !important; }
    li[role="option"]:hover { background-color: #FF2800 !important; color: white !important; }
    span[data-baseweb="tag"] { background-color: #FF2800 !important; color: white !important; border: none !important; }
    .stRadio > div { background-color: #111111; border-left: 3px solid #FF2800; padding: 10px; border-radius: 5px; }
    div[data-testid="stTable"] { background-color: #111111; border-radius: 5px; border: 1px solid #333333; }
    button[kind="primary"] { background-color: #FF2800 !important; color: white !important; border: none !important; font-family: 'Anton', sans-serif !important; letter-spacing: 1px; }
    button[kind="primary"]:hover { background-color: #cc2000 !important; }
    input { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

DRIVER_COLORS = {
    'VER': '#1e41ff', 'PER': '#00155e', 'HAD': '#00155e',
    'LEC': '#ff0000', 'HAM': '#800000', 'SAI': '#cc0000',
    'NOR': '#ff8700', 'PIA': '#8c4a00',
    'RUS': '#00d2be', 'ANT': '#005951',
    'ALO': '#006f62', 'STR': '#00332d',
    'TSU': '#6692ff', 'LAW': '#1a41b3', 'RIC': '#1a41b3',
    'ALB': '#005aff', 'COL': '#002566',
    'GAS': '#ff69b4', 'DOO': '#992663', 'OCO': '#992663',
    'BOT': '#52e252', 'ZHO': '#1c661c', 'BOR': '#52e252',
    'HUL': '#ffffff', 'MAG': '#666666', 'BEA': '#666666', 'OEA': '#666666'
}


# ==============================================================================
# 3. MOTORE DATI E PRESELEZIONE EVENTO AUTOMATICA (WEEKEND SUCCESSIVO)
# ==============================================================================
@st.cache_data(ttl=3600)
def get_schedule_data(year):
    try:
        schedule = fastf1.get_event_schedule(year)
        schedule = schedule[schedule['EventName'] != 'TBC']
        return schedule
    except Exception as e:
        st.sidebar.error(f"Errore caricamento calendario: {e}")
        return pd.DataFrame()


@st.cache_resource(show_spinner=False)
def load_session_data(year, event_name, session_identifier, is_test=False, test_number=1):
    try:
        if is_test:
            session = fastf1.get_testing_session(year, test_number, session_identifier)
        else:
            schedule = fastf1.get_event_schedule(year)
            event_matches = schedule[schedule['EventName'] == event_name]
            if not event_matches.empty:
                exact_event = event_matches.iloc[0]
                session = exact_event.get_session(session_identifier)
            else:
                session = fastf1.get_session(year, event_name, session_identifier)

        session.load(telemetry=True, weather=True, messages=False)
        _ = session.laps
        return session, "OK"
    except DataNotLoadedError:
        return None, "I server F1 non hanno ancora rilasciato i file timing ufficiali."
    except Exception as e:
        return None, str(e)


def process_laps(session):
    if session is None: return pd.DataFrame()
    try:
        laps = session.laps
        if laps.empty: return pd.DataFrame()
        laps['LapTimeSec'] = laps['LapTime'].dt.total_seconds()
        laps['Sector1TimeSec'] = laps['Sector1Time'].dt.total_seconds()
        laps['Sector2TimeSec'] = laps['Sector2Time'].dt.total_seconds()
        laps['Sector3TimeSec'] = laps['Sector3Time'].dt.total_seconds()
        return laps
    except Exception:
        return pd.DataFrame()


def get_telemetry_for_lap(lap):
    try:
        tel = lap.get_telemetry()
        tel['SpeedMS'] = tel['Speed'] / 3.6
        tel['dt'] = tel['Time'].dt.total_seconds().diff().fillna(0.1)
        tel['Acc'] = tel['SpeedMS'].diff() / tel['dt']
        tel['Acc_Smooth'] = tel['Acc'].rolling(window=5, center=True).mean().fillna(0)
        tel['PowerFactor'] = tel['Acc_Smooth'] * tel['SpeedMS']
        return tel
    except:
        return pd.DataFrame()


def get_weather_history(session):
    if session is None: return pd.DataFrame()
    try:
        return session.weather_data
    except Exception:
        return pd.DataFrame()


# ==============================================================================
# 4. UI & SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown(f'<img src="{LOGO_URL}" width="180">', unsafe_allow_html=True)
    st.write("")
    st.header("1. SESSIONE (FASTF1)")

    sel_year = st.selectbox("Anno", [2026, 2025, 2024], index=0)

    with st.spinner("Scarico Calendario Ufficiale..."):
        schedule = get_schedule_data(sel_year)

    events_mapping = {}
    test_number = 1
    events_list = []
    default_event_idx = 0

    if not schedule.empty:
        # Costruzione Mapping Eventi
        test_events = schedule[schedule['EventName'].str.contains("Test", case=False, na=False)]
        test_count = 1
        for _, r in test_events.iterrows():
            ui_label = f"TEST: Bahrain {test_count}"
            events_mapping[ui_label] = r['EventName']
            test_count += 1

        if sel_year == 2026 and len(test_events) < 2:
            events_mapping["TEST: Bahrain 1"] = "Pre-Season Testing 1"
            events_mapping["TEST: Bahrain 2"] = "Pre-Season Testing 2"

        gps = schedule[(schedule['RoundNumber'] > 0) & (~schedule['EventName'].str.contains("Test", case=False, na=False))]
        for _, r in gps.iterrows():
            ui_label = f"R{r['RoundNumber']}: {r['EventName']}"
            events_mapping[ui_label] = r['EventName']

        events_list = list(events_mapping.keys())

        # CALCOLO AUTO-SELEZIONE GRAN PREMIO SUCCESSIVO/CORRENTE
        try:
            now = pd.Timestamp.now().tz_localize(None)
            # Prendi gli eventi futuri o appena passati (tolleranza 3 giorni per coprire il weekend corrente)
            upcoming_events = schedule[schedule['EventDate'].dt.tz_localize(None) >= now - pd.Timedelta(days=3)]
            if not upcoming_events.empty:
                next_event_name = upcoming_events.iloc[0]['EventName']
                for i, ev_label in enumerate(events_list):
                    if next_event_name in ev_label:
                        default_event_idx = i
                        break
        except Exception:
            default_event_idx = 0  # Fallback al primo evento

        sel_event_label = st.selectbox("Evento", events_list, index=default_event_idx)
        event_name_for_api = events_mapping[sel_event_label]
        is_test = "TEST:" in sel_event_label

        if is_test:
            try:
                test_number = int(sel_event_label.split()[-1])
            except ValueError:
                test_number = 1

            st.info("💡 Modalità Test: Giorni forzati")
            session_opts = ['Day 1', 'Day 2', 'Day 3']
            sel_session_display = st.selectbox("Giorno di Test", session_opts, index=0)
            if sel_session_display == 'Day 1':
                session_identifier = 1
            elif sel_session_display == 'Day 2':
                session_identifier = 2
            elif sel_session_display == 'Day 3':
                session_identifier = 3
        else:
            session_opts = []
            event_row = schedule[schedule['EventName'] == event_name_for_api].iloc[0]
            for i in range(1, 6):
                s_name = event_row.get(f'Session{i}')
                if pd.notna(s_name) and str(s_name).strip() not in ['', 'None']:
                    session_opts.append(str(s_name).strip())

            if not session_opts:
                session_opts = ['Practice 1', 'Practice 2', 'Practice 3', 'Qualifying', 'Race']

            # Seleziona l'ultima sessione disponibile per default (solitamente Gara o l'ultima finita)
            sel_session_display = st.selectbox("Sessione Ufficiale", session_opts, index=len(session_opts) - 1 if session_opts else 0)
            session_identifier = sel_session_display
    else:
        st.error("Impossibile caricare il calendario.")
        st.stop()

    st.divider()

    load_btn = st.button("🔌 CONNETTI & CARICA DATI", type="primary", use_container_width=True)

    if 'session_loaded' not in st.session_state:
        st.session_state['session_loaded'] = None

    if load_btn:
        with st.status("Stabilendo connessione ai server F1...", expanded=True) as status:
            session_obj, error_msg = load_session_data(sel_year, event_name_for_api, session_identifier, is_test, test_number)
            if session_obj is not None:
                st.session_state['session_loaded'] = session_obj
                status.update(label="Dati scaricati con successo!", state="complete", expanded=False)
            else:
                st.session_state['session_loaded'] = None
                status.update(label=f"Errore caricamento: {error_msg}", state="error")

    st.header("2. ANALISI")
    tool = st.radio("Strumento", [
        "TELEMETRIA PRO",
        "PACE PERFORMANCE",
        "STRATEGIE",
        "METEO",
        "CORNER ANALYSES",
        "ENERGY ANALYSES",
        "TRACTION ANALYSES",
        "SPEED",
        "BEST SECTORS",
        "G_LONGITUDINAL",
        "GLATERAL",
        "CIRCLE",
        "TIRE DEGRADATION",
        "SIMULAZIONE PASSO GARA",
        "PASSO GARA",
        "RACE TRACE",
        "MICROSECTORS MAP",
        "TELEMETRY DIFF SESSION"
    ])

    st.header("3. DRIVERS")

    # NUOVI PILOTI DI DEFAULT COME RICHIESTO
    desired_defaults = ['LEC', 'HAM', 'NOR', 'PIA', 'RUS', 'ANT', 'VER', 'HAD']
    available_drivers = desired_defaults.copy()
    default_drivers = desired_defaults.copy()

    if st.session_state['session_loaded']:
        try:
            session_laps = st.session_state['session_loaded'].laps
            if not session_laps.empty:
                available_drivers = sorted(session_laps['Driver'].dropna().unique())
                # Filtra i default per evitare errori se un pilota non ha girato
                default_drivers = [d for d in desired_defaults if d in available_drivers]
                if not default_drivers:
                    default_drivers = available_drivers[:2] if len(available_drivers) > 1 else available_drivers
        except Exception:
            pass

    sel_drivers = st.multiselect("Piloti", available_drivers, default=default_drivers)
    custom_colors = {d: DRIVER_COLORS.get(d, '#FFFFFF') for d in sel_drivers}


# ==============================================================================
# FUNZIONI HELPER PER TITOLO E WATERMARK
# ==============================================================================
def get_chart_title(tool_name):
    return f"{sel_year} {sel_event_label} {sel_session_display} | {tool_name} - @FormulaTecnica"


def get_watermark():
    # Fix Plotly Base64 Bug: Utilizza PIL Image per il rendering SVG Plotly se il file locale esiste
    try:
        if os.path.exists(LOGO_FILENAME):
            img = Image.open(LOGO_FILENAME)
        else:
            img = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/F1.svg/320px-F1.svg.png"
    except Exception:
        img = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/F1.svg/320px-F1.svg.png"

    return [dict(
        source=img,
        xref="paper", yref="paper",
        # SPOSTAMENTO LOGO: Verticalmente circa a metà (0.5), leggermente più in basso.
        # Spostato da y=1.08 (fuori in alto) a y=0.42 (all'interno del grafico)
        x=1.0, y=0.42,
        sizex=0.20, sizey=0.20,
        xanchor="right", yanchor="bottom"  # Ancoraggio in basso rispetto alla coordinata y
    )]


# --- SEZIONE 4. TRACK ---
st.header("4. TRACK")
if st.session_state['session_loaded'] and tool != "MICROSECTORS MAP":
    try:
        with st.spinner("Generazione mappa..."):
            sess = st.session_state['session_loaded']
            fastest_lap = sess.laps.pick_fastest()

            if pd.notna(fastest_lap.get('LapTime')):
                tel = fastest_lap.get_telemetry()

                try:
                    circuit_info = sess.get_circuit_info()
                    corners = circuit_info.corners
                except:
                    corners = pd.DataFrame()

                fig_track = go.Figure()

                fig_track.add_trace(go.Scatter(
                    x=tel['X'], y=tel['Y'],
                    mode='markers',
                    marker=dict(
                        size=4,
                        color=tel['Speed'],
                        colorscale='inferno',
                        showscale=False
                    ),
                    hoverinfo='skip'
                ))

                if not corners.empty and 'X' in corners.columns and 'Y' in corners.columns:
                    for _, corner in corners.iterrows():
                        c_num = str(corner.get('Number', '')).replace('.0', '')
                        c_let = str(corner.get('Letter', '')).replace('nan', '')

                        fig_track.add_annotation(
                            x=corner['X'], y=corner['Y'],
                            text=f"{c_num}{c_let}",
                            showarrow=False,
                            font=dict(color='white', size=11, family="Anton"),
                            bgcolor="#FF2800",
                            borderpad=2,
                            bordercolor="white",
                            borderwidth=1
                        )

                fig_track.update_layout(
                    title=get_chart_title("Track Map"),
                    # Watermark non aggiunto qui per pulizia della mappa, ma disponibile
                    template="plotly_dark",
                    paper_bgcolor='#0f0f0f',
                    plot_bgcolor='#0f0f0f',
                    margin=dict(l=0, r=0, t=60, b=0),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
                    height=280
                )
                st.plotly_chart(fig_track, use_container_width=True)
                st.markdown(
                    "<div style='font-size:12px; color:#aaa; font-family: Roboto Mono; text-align: center; margin-top:-10px;'>💡 Colori chiari/gialli = Rettilinei (Alta Vel.)<br>Colori scuri = Curve (Bassa Vel.)</div>",
                    unsafe_allow_html=True)
    except Exception as e:
        st.warning("Mappa del tracciato non disponibile.")

title_txt = f"{sel_year} {sel_event_label} - {sel_session_display} | @PITWALLDATA"
st.markdown(
    f"""<div style="border-bottom:3px solid #FF2800;padding:15px;background:#111;display:flex;align-items:center;margin-bottom:20px;"><img src="{LOGO_URL}" height="80" style="margin-right:20px"><span style="font-size:26px;color:white;font-family:'Anton';letter-spacing:1px;">{title_txt}</span></div>""",
    unsafe_allow_html=True)

session = st.session_state['session_loaded']
if not session:
    st.info("👈 Seleziona un evento e clicca 'CONNETTI & CARICA DATI' nella barra laterale.")
    st.stop()

laps = process_laps(session)
if laps.empty:
    st.warning("Dati non ancora disponibili dai server ufficiali.")
    st.stop()

# ==============================================================================
# TOOL 1: TELEMETRIA PRO
# ==============================================================================
if tool == "TELEMETRIA PRO":
    col_ctrl, col_plot = st.columns([1.5, 5])

    selected_laps_dict = {}
    plot_data = []

    peak_x_list = []
    valley_x_list = []

    with col_ctrl:
        st.subheader("IMPOSTAZIONI")

        sel_ch_input = st.multiselect("Canali", ['Delta', 'Speed', 'Throttle', 'Brake', 'RPM', 'nGear', 'PowerFactor'],
                                      default=['Delta', 'Speed', 'Throttle', 'Brake'])

        show_delta = 'Delta' in sel_ch_input
        sel_ch = [ch for ch in sel_ch_input if ch != 'Delta']

        st.markdown("---")
        st.subheader("SELEZIONE GIRI")

        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
            if not d_laps.empty:
                fastest_idx = d_laps['LapTimeSec'].idxmin()
                best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                col = custom_colors.get(driver, "#FFF")

                st.markdown(
                    f"<div style='border-left:4px solid {col};padding-left:10px; margin-top:10px; background:#1a1a1a;'><b>{driver}</b></div>",
                    unsafe_allow_html=True)

                opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                def_opt = next((opt for opt in opts if opt[0] == best_lap_num), None)

                sel_laps_info = st.multiselect(
                    f"Giri ({driver})", opts, default=[def_opt] if def_opt else [],
                    format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s", key=f"ml_{driver}"
                )

                for lap_info in sel_laps_info:
                    sel_ln = lap_info[0]
                    lap_time_sec = lap_info[1]
                    target_lap = d_laps[d_laps['LapNumber'] == sel_ln].iloc[0]

                    lap_key = f"{driver} L{int(sel_ln)}"
                    selected_laps_dict[lap_key] = {
                        'driver': driver, 'lap': target_lap, 'color': col,
                        'time': f"{lap_time_sec:.3f}s", 'lap_time_sec': lap_time_sec
                    }

    with col_plot:
        if selected_laps_dict:
            ref_key = min(selected_laps_dict, key=lambda k: selected_laps_dict[k]['lap_time_sec'])
            ref_lap = selected_laps_dict[ref_key]['lap']

            with st.spinner("Elaborazione Telemetria, Delta e calcolo curve..."):
                ref_tel = get_telemetry_for_lap(ref_lap)

                if not ref_tel.empty:
                    ref_dist = ref_tel['Distance'].values
                    ref_time = ref_tel['Time'].dt.total_seconds().values

                    ref_peaks_idx, _ = signal.find_peaks(ref_tel['Speed'], distance=40, prominence=15)
                    ref_valleys_idx, _ = signal.find_peaks(-ref_tel['Speed'], distance=40, prominence=15)

                    peak_x_list = ref_tel['Distance'].iloc[ref_peaks_idx].values
                    valley_x_list = ref_tel['Distance'].iloc[ref_valleys_idx].values

                    for lap_key, info in selected_laps_dict.items():
                        comp_lap = info['lap']
                        comp_tel = get_telemetry_for_lap(comp_lap)

                        if not comp_tel.empty:
                            is_ref = (lap_key == ref_key)

                            if is_ref:
                                delta_time = np.zeros(len(ref_dist))
                            else:
                                comp_dist = comp_tel['Distance'].values
                                comp_time = comp_tel['Time'].dt.total_seconds().values
                                _, unique_indices = np.unique(comp_dist, return_index=True)
                                comp_time_interp = np.interp(ref_dist, comp_dist[unique_indices],
                                                             comp_time[unique_indices])
                                delta_time = comp_time_interp - ref_time

                            plot_data.append({
                                'label': lap_key,
                                'data': comp_tel,
                                'delta': delta_time,
                                'color': info['color'],
                                'time': info['time'],
                                'is_ref': is_ref,
                                'line_width': 3 if is_ref else 1.5
                            })

            n_rows = len(sel_ch) + (1 if show_delta else 0)

            if n_rows > 0 and plot_data:
                fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)
                start_row_for_channels = 2 if show_delta else 1

                if show_delta:
                    for item in plot_data:
                        prefix = "Ref" if item['is_ref'] else "Gap"
                        fig.add_trace(go.Scatter(
                            x=ref_dist, y=item['delta'], mode='lines',
                            name=f"{prefix} {item['label']} ({item['time']})",
                            line=dict(color=item['color'], width=item['line_width']),
                            legendgroup=item['label'], showlegend=True
                        ), row=1, col=1)

                    fig.update_yaxes(title_text="Delta (s)", row=1, col=1)
                    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3, row=1, col=1)

                for idx, item in enumerate(plot_data):
                    df = item['data']
                    for i, ch in enumerate(sel_ch):
                        target_row = i + start_row_for_channels
                        show_leg = (not show_delta) and (i == 0)
                        legend_name = f"{item['label']} ({item['time']})" if show_leg else item['label']

                        if ch in df.columns:
                            fig.add_trace(go.Scatter(
                                x=df['Distance'], y=df[ch], mode='lines',
                                name=legend_name,
                                line=dict(color=item['color'], width=item['line_width']),
                                legendgroup=item['label'], showlegend=show_leg
                            ), row=target_row, col=1)

                            if ch == 'Speed':
                                drv_peak_x, drv_peak_y, drv_peak_txt = [], [], []
                                for px in peak_x_list:
                                    mask = (df['Distance'] > px - 50) & (df['Distance'] < px + 50)
                                    if mask.any():
                                        local_max = df[ch][mask].max()
                                        drv_peak_x.append(px)
                                        drv_peak_y.append(local_max + 8 + (idx * 14))
                                        drv_peak_txt.append(f"{int(local_max)}")

                                if drv_peak_x:
                                    fig.add_trace(go.Scatter(
                                        x=drv_peak_x, y=drv_peak_y, mode='text',
                                        text=drv_peak_txt, textposition='top center',
                                        showlegend=False, hoverinfo='skip',
                                        textfont=dict(color=item['color'], size=11, family="Roboto Mono")
                                    ), row=target_row, col=1)

                                drv_valley_x, drv_valley_y, drv_valley_txt = [], [], []
                                for vx in valley_x_list:
                                    mask = (df['Distance'] > vx - 50) & (df['Distance'] < vx + 50)
                                    if mask.any():
                                        local_min = df[ch][mask].min()
                                        drv_valley_x.append(vx)
                                        drv_valley_y.append(local_min - 8 - (idx * 14))
                                        drv_valley_txt.append(f"{int(local_min)}")

                                if drv_valley_x:
                                    fig.add_trace(go.Scatter(
                                        x=drv_valley_x, y=drv_valley_y, mode='text',
                                        text=drv_valley_txt, textposition='bottom center',
                                        showlegend=False, hoverinfo='skip',
                                        textfont=dict(color=item['color'], size=11, family="Roboto Mono")
                                    ), row=target_row, col=1)

                            if idx == 0:
                                units = {'Speed': 'km/h', 'Throttle': '%', 'Brake': '%', 'RPM': 'rpm', 'PowerFactor': 'W/kg'}
                                fig.update_yaxes(title_text=f"{ch} [{units.get(ch, '')}]", row=target_row, col=1)

                fig.update_layout(
                    title=get_chart_title("Telemetria Pro"),
                    images=get_watermark(),
                    height=250 * n_rows,
                    template="plotly_dark", paper_bgcolor='#000', plot_bgcolor='#0a0a0a',
                    margin=dict(r=20, t=70), hovermode="x unified",
                    legend=dict(orientation="h", y=1.02, x=0, xanchor="left", yanchor="bottom")
                )
                st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# TOOL 2: PACE PERFORMANCE
# ==============================================================================
elif tool == "PACE PERFORMANCE":
    st.subheader("📊 ANALISI PASSO GARA")
    drivers_laps = laps[laps['Driver'].isin(sel_drivers)].copy()
    if not drivers_laps.empty:
        col_flags, col_radio = st.columns([1, 3])
        stint_options = ["Tutta la gara"] + [f"Stint {i}" for i in range(1, 11)]

        with col_radio:
            selected_global_stint = st.radio("Seleziona Stint", options=stint_options, horizontal=True, key="pace_perf_stint")

        if selected_global_stint != "Tutta la gara":
            target_stint_num = int(selected_global_stint.split(" ")[1])
            if 'Stint' in drivers_laps.columns:
                drivers_laps = drivers_laps[drivers_laps['Stint'] == target_stint_num]

        if not drivers_laps.empty:
            threshold = drivers_laps['LapTimeSec'].median() * 1.10
            clean_laps = drivers_laps[drivers_laps['LapTimeSec'] < threshold]
            if not clean_laps.empty:
                fig_viol = px.box(clean_laps, x="Driver", y="LapTimeSec", color="Driver", points="all",
                                  color_discrete_map=custom_colors)
                fig_viol.update_layout(
                    title=get_chart_title(f"Distribuzione Tempi - {selected_global_stint}"),
                    images=get_watermark(),
                    showlegend=False, template="plotly_dark",
                    paper_bgcolor='#0f0f0f', plot_bgcolor='#111', margin=dict(t=70)
                )
                st.plotly_chart(fig_viol, use_container_width=True)
            else:
                st.warning(f"Nessun tempo valido (senza traffico/SC) trovato per i piloti in {selected_global_stint}.")
        else:
            st.warning(f"Nessun giro registrato o stint inesistente per i piloti in {selected_global_stint}.")

# ==============================================================================
# TOOL 3: STRATEGIE (Tyre History)
# ==============================================================================
elif tool == "STRATEGIE":
    st.subheader("🍩 UTILIZZO GOMME & STINT")
    if 'Compound' in laps.columns:
        fig = go.Figure()
        for i, driver in enumerate(sel_drivers):
            d_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
            if d_laps.empty: continue
            d_laps['stint_change'] = d_laps['Compound'] != d_laps['Compound'].shift()
            d_laps['stint_id'] = d_laps['stint_change'].cumsum()
            stints = d_laps.groupby('stint_id').agg({'Compound': 'first', 'LapNumber': ['min', 'max']}).reset_index()
            stints.columns = ['stint_id', 'Compound', 'LapStart', 'LapEnd']

            for _, s in stints.iterrows():
                dur = s['LapEnd'] - s['LapStart'] + 1
                bar_col = {'SOFT': '#da291c', 'MEDIUM': '#ffd100', 'HARD': '#f0f0f0', 'INTERMEDIATE': '#43b02a',
                           'WET': '#0067a5'}.get(s['Compound'], '#888')
                fig.add_trace(
                    go.Bar(y=[driver], x=[dur], base=[s['LapStart']], orientation='h', marker=dict(color=bar_col),
                           name=s['Compound'], showlegend=False))

        fig.update_layout(
            title=get_chart_title("Cronologia Stint"),
            images=get_watermark(),
            barmode='stack', template="plotly_dark", paper_bgcolor='#0f0f0f',
            plot_bgcolor='#111', margin=dict(t=70)
        )
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# TOOL 4: METEO
# ==============================================================================
elif tool == "METEO":
    st.subheader("🌤️ CONDIZIONI METEO SESSIONE")
    w_data = get_weather_history(session)
    if not w_data.empty:
        w_data['Minutes'] = w_data['Time'].dt.total_seconds() / 60
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=w_data['Minutes'], y=w_data['TrackTemp'], name="Track Temp", line=dict(color='red')))
        fig.add_trace(go.Scatter(x=w_data['Minutes'], y=w_data['AirTemp'], name="Air Temp", line=dict(color='cyan')))
        fig.update_layout(
            title=get_chart_title("Evoluzione Meteo"),
            images=get_watermark(),
            template="plotly_dark", paper_bgcolor='#0f0f0f', plot_bgcolor='#111', margin=dict(t=70)
        )
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# TOOL 5: CORNER ANALYSES
# ==============================================================================
elif tool == "CORNER ANALYSES":
    st.subheader("🏁 CORNER ANALYSES (Velocità Minima in Curva)")

    with st.spinner("Estrazione dati tracciato e calcolo velocità..."):
        try:
            circuit_info = session.get_circuit_info()
            corners = circuit_info.corners
            if 'Number' in corners.columns and 'Distance' in corners.columns:
                corners = corners.dropna(subset=['Distance'])
            else:
                corners = pd.DataFrame()
        except Exception as e:
            st.warning("Informazioni sulle curve del circuito non disponibili per questa specifica sessione o test.")
            corners = pd.DataFrame()

        if not corners.empty:
            st.info(
                f"💡 Vengono analizzati i giri completi dei piloti attualmente selezionati: {', '.join(sel_drivers)}.")

            results = []
            drivers_laps = laps[laps['Driver'].isin(sel_drivers)].dropna(subset=['LapTimeSec'])
            drivers_laps = drivers_laps.sort_values(['Driver', 'LapNumber'])

            total_laps = len(drivers_laps)
            if total_laps > 0:
                progress_bar = st.progress(0)

                for idx, (_, lap) in enumerate(drivers_laps.iterrows()):
                    driver = lap['Driver']
                    lap_num = lap['LapNumber']
                    lap_time = lap['LapTimeSec']

                    try:
                        tel = lap.get_telemetry()
                        if not tel.empty:
                            row_data = {
                                'Driver': driver,
                                'Lap': int(lap_num),
                                'LapTime (s)': round(lap_time, 3)
                            }

                            for _, corner in corners.iterrows():
                                c_num = str(corner.get('Number', '')).replace('.0', '')
                                c_let = str(corner.get('Letter', '')).replace('nan', '')
                                c_name = f"T{c_num}{c_let}" if c_num else f"T_unk"

                                c_dist = corner['Distance']

                                mask = (tel['Distance'] >= c_dist - 100) & (tel['Distance'] <= c_dist + 100)
                                if mask.any():
                                    min_speed = tel.loc[mask, 'Speed'].min()
                                    row_data[f'{c_name} (km/h)'] = int(min_speed)
                                else:
                                    row_data[f'{c_name} (km/h)'] = None

                            results.append(row_data)
                    except Exception:
                        pass

                    progress_bar.progress((idx + 1) / total_laps)

                progress_bar.empty()

                if results:
                    df_results = pd.DataFrame(results)

                    corner_cols = [col for col in df_results.columns if '(km/h)' in col]


                    def highlight_max_purple(s):
                        is_max = s == s.max()
                        return ['background-color: #8A2BE2; color: white; font-weight: bold;' if v else '' for v in
                                is_max]


                    styled_df = df_results.style.set_properties(**{
                        'background-color': '#1a1a1a',
                        'color': '#cccccc',
                        'border-color': '#333333'
                    }).apply(highlight_max_purple, subset=corner_cols)

                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.warning("Nessun dato di telemetria estraibile per questi giri.")
            else:
                st.warning("Nessun giro valido registrato per i piloti selezionati in questa sessione.")

# ==============================================================================
# TOOL 6: ENERGY ANALYSES
# ==============================================================================
elif tool == "ENERGY ANALYSES":
    st.subheader("⚡ ENERGY ANALYSES (Deployment & Harvesting)")
    st.markdown("Calcolo dell'energia specifica spesa e recuperata (J/kg) integrando il Power Factor lungo il giro.")

    col_sel, col_tab = st.columns([1.5, 4])
    selected_laps_to_analyze = []

    with col_sel:
        st.markdown(
            "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>SELEZIONA GIRO</b></div>",
            unsafe_allow_html=True)
        st.write("")

        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
            if not d_laps.empty:
                fastest_idx = d_laps['LapTimeSec'].idxmin()
                best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                col_drv = custom_colors.get(driver, "#FFF")

                opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                def_opt_idx = next((i for i, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>", unsafe_allow_html=True)
                sel_lap_info = st.selectbox(
                    f"Giro per {driver}",
                    opts,
                    index=def_opt_idx,
                    format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                    key=f"energy_lap_{driver}",
                    label_visibility="collapsed"
                )
                st.write("")

                target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                selected_laps_to_analyze.append({
                    'Driver': driver,
                    'Lap': int(sel_lap_info[0]),
                    'LapTime': sel_lap_info[1],
                    'lap_obj': target_lap
                })

    with col_tab:
        if selected_laps_to_analyze:
            results = []
            with st.spinner("Integrazione della potenza per il calcolo dell'energia..."):
                for item in selected_laps_to_analyze:
                    tel = get_telemetry_for_lap(item['lap_obj'])

                    if not tel.empty and 'PowerFactor' in tel.columns and 'dt' in tel.columns:
                        mask_pos = tel['PowerFactor'] > 0
                        deployment = (tel.loc[mask_pos, 'PowerFactor'] * tel.loc[mask_pos, 'dt']).sum()

                        mask_neg = tel['PowerFactor'] < 0
                        harvesting = (tel.loc[mask_neg, 'PowerFactor'] * tel.loc[mask_neg, 'dt']).sum()

                        results.append({
                            'Driver': item['Driver'],
                            'Lap': item['Lap'],
                            'LapTime (s)': f"{item['LapTime']:.3f}",
                            'Deployment (J/kg)': int(deployment),
                            'Harvesting (J/kg)': int(abs(harvesting)),
                            'Net Energy (J/kg)': int(deployment + harvesting)
                        })

            if results:
                df_energy = pd.DataFrame(results)


                def highlight_deployment(s):
                    is_max = s == s.max()
                    return ['color: #FF2800; font-weight: bold;' if v else '' for v in is_max]


                def highlight_harvesting(s):
                    is_max = s == s.max()
                    return ['color: #00d2be; font-weight: bold;' if v else '' for v in is_max]


                styled_df = df_energy.style.set_properties(**{
                    'background-color': '#1a1a1a',
                    'color': '#cccccc',
                    'border-color': '#333333',
                    'text-align': 'center'
                }) \
                    .apply(highlight_deployment, subset=['Deployment (J/kg)']) \
                    .apply(highlight_harvesting, subset=['Harvesting (J/kg)'])

                st.dataframe(styled_df, use_container_width=True, hide_index=True)

                dl_filename = generate_filename(sel_year, event_name_for_api, is_test, test_number, sel_session_display,
                                                "ENERGY", sel_drivers)
                img_buf = create_image_from_df(df_energy, "Energy Analyses")
                st.download_button(
                    label="📸 Scarica Tabella come Immagine",
                    data=img_buf,
                    file_name=dl_filename,
                    mime="image/png"
                )

                st.info(
                    "💡 **Deployment (Rosso):** Chi ha il valore più alto sta spendendo più energia elettrica/motore nel giro. \n\n"
                    "💡 **Harvesting (Azzurro):** Chi ha il valore più alto sta rigenerando più energia in frenata.\n\n"
                    "💡 **Net Energy:** Differenza tra speso e recuperato. Un numero più alto indica un giro che svuota maggiormente la batteria (State of Charge).")
            else:
                st.warning("Dati telemetrici incompleti per effettuare il calcolo dell'energia.")


# ==============================================================================
# TOOL 7: TRACTION ANALYSES
# ==============================================================================
elif tool == "TRACTION ANALYSES":
    st.subheader("🚀 TRACTION ANALYSES (Distanza Apex -> 100% Throttle)")
    st.markdown(
        "Analisi della trazione: seleziona una singola curva per confrontare quanti metri impiegano i piloti dall'apice per tornare a tavoletta (100% acceleratore).")

    col_sel, col_tab = st.columns([1.5, 4])
    selected_laps_to_analyze = []

    with col_sel:
        st.markdown(
            "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>IMPOSTAZIONI</b></div>",
            unsafe_allow_html=True)
        st.write("")

        sel_corner = st.selectbox("Seleziona Curva", [str(i) for i in range(1, 16)], index=0,
                                  format_func=lambda x: f"Curva {x}")

        st.markdown("---")
        analisi_mode = st.radio("Modalità di Analisi",
                                ["Singolo Giro (Selezionato)", "Miglior Valore (Entro 2s dal Best)"],
                                help="Scegli se analizzare un giro specifico o cercare il miglior valore tra i giri 'push' veri (entro 2 secondi dal best lap personale).")
        st.markdown("---")

        if analisi_mode == "Singolo Giro (Selezionato)":
            for driver in sel_drivers:
                d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
                if not d_laps.empty:
                    fastest_idx = d_laps['LapTimeSec'].idxmin()
                    best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                    col_drv = custom_colors.get(driver, "#FFF")

                    opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                    def_opt_idx = next((i for i, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                    st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>",
                                unsafe_allow_html=True)
                    sel_lap_info = st.selectbox(
                        f"Giro per {driver}",
                        opts,
                        index=def_opt_idx,
                        format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                        key=f"trac_lap_{driver}",
                        label_visibility="collapsed"
                    )
                    st.write("")

                    target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                    selected_laps_to_analyze.append({
                        'Driver': driver,
                        'Lap': str(int(sel_lap_info[0])),
                        'LapTime': sel_lap_info[1],
                        'lap_obj': target_lap
                    })
        else:
            st.info(
                "⚡ **Analisi ultra-ottimizzata:** Verranno scansionati ESCLUSIVAMENTE i giri con un distacco massimo di 2.0 secondi dal record personale del pilota, ignorando tutto il resto.")

    with col_tab:
        if (analisi_mode == "Singolo Giro (Selezionato)" and selected_laps_to_analyze) or (
                analisi_mode == "Miglior Valore (Entro 2s dal Best)"):
            with st.spinner(f"Estrazione telemetria e calcolo trazione per Curva {sel_corner}..."):
                try:
                    circuit_info = session.get_circuit_info()
                    corners = circuit_info.corners
                    if 'Number' in corners.columns and 'Distance' in corners.columns:
                        corners = corners.dropna(subset=['Distance'])
                        corners['NumberStr'] = corners['Number'].astype(str).str.replace('.0', '', regex=False)
                    else:
                        corners = pd.DataFrame()
                except Exception:
                    corners = pd.DataFrame()

                if corners.empty:
                    st.warning("Informazioni sulle curve del circuito non disponibili.")
                else:
                    corner_data = corners[corners['NumberStr'] == sel_corner]

                    if corner_data.empty:
                        st.warning(f"Curva {sel_corner} non trovata nei dati del tracciato per questo circuito.")
                    else:
                        c_dist = corner_data.iloc[0]['Distance']
                        c_name = f"T{sel_corner}"
                        all_results = []

                        if analisi_mode == "Singolo Giro (Selezionato)":
                            # --- LOGICA ORIGINALE: SINGOLO GIRO ---
                            for item in selected_laps_to_analyze:
                                tel = get_telemetry_for_lap(item['lap_obj'])
                                if tel.empty or 'Throttle' not in tel.columns:
                                    continue

                                mask_apex = (tel['Distance'] >= c_dist - 100) & (tel['Distance'] <= c_dist + 100)
                                if not mask_apex.any():
                                    continue

                                apex_idx = tel.loc[mask_apex, 'Speed'].idxmin()
                                apex_dist = tel.loc[apex_idx, 'Distance']
                                min_speed = tel.loc[apex_idx, 'Speed']
                                min_gear = tel.loc[mask_apex, 'nGear'].min()

                                post_apex_tel = tel.loc[apex_idx:].copy()

                                mask_ft = post_apex_tel['Throttle'] >= 99
                                if mask_ft.any():
                                    ft_idx = mask_ft.idxmax()
                                    dist_to_ft = tel.loc[ft_idx, 'Distance'] - apex_dist
                                else:
                                    dist_to_ft = np.nan

                                all_results.append({
                                    'Driver': item['Driver'],
                                    'Lap': item['Lap'],
                                    'Min Speed (km/h)': int(min_speed),
                                    'Min Gear': int(min_gear) if pd.notna(min_gear) else None,
                                    'Dist to 100% Thr. (m)': round(dist_to_ft, 1) if pd.notna(dist_to_ft) else None
                                })

                        else:
                            # --- NUOVA LOGICA: MIGLIOR VALORE SUI GIRI ENTRO I 2 SECONDI ---
                            progress_bar = st.progress(0)
                            total_drivers = len(sel_drivers)

                            for d_idx, driver in enumerate(sel_drivers):
                                d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
                                best_dist = float('inf')
                                best_lap_data = None

                                if not d_laps.empty:
                                    # FILTRO ESTREMO: solo i giri <= (Miglior Tempo + 1.5 secondi)
                                    fastest_time = d_laps['LapTimeSec'].min()
                                    d_laps = d_laps[d_laps['LapTimeSec'] <= fastest_time + 1.5]

                                    for _, lap_row in d_laps.iterrows():
                                        try:
                                            tel = get_telemetry_for_lap(lap_row)
                                            if tel.empty or 'Throttle' not in tel.columns:
                                                continue

                                            mask_apex = (tel['Distance'] >= c_dist - 100) & (
                                                    tel['Distance'] <= c_dist + 100)
                                            if not mask_apex.any():
                                                continue

                                            apex_idx = tel.loc[mask_apex, 'Speed'].idxmin()
                                            apex_dist = tel.loc[apex_idx, 'Distance']
                                            min_speed = tel.loc[apex_idx, 'Speed']
                                            min_gear = tel.loc[mask_apex, 'nGear'].min()

                                            post_apex_tel = tel.loc[apex_idx:].copy()

                                            mask_ft = post_apex_tel['Throttle'] >= 99
                                            if mask_ft.any():
                                                ft_idx = mask_ft.idxmax()
                                                dist_to_ft = tel.loc[ft_idx, 'Distance'] - apex_dist

                                                # Se troviamo una trazione migliore (meno metri) e positiva
                                                if 0 < dist_to_ft < best_dist:
                                                    best_dist = dist_to_ft
                                                    best_lap_data = {
                                                        'Driver': driver,
                                                        'Lap': f"{int(lap_row['LapNumber'])} (Best)",
                                                        'Min Speed (km/h)': int(min_speed),
                                                        'Min Gear': int(min_gear) if pd.notna(min_gear) else None,
                                                        'Dist to 100% Thr. (m)': round(dist_to_ft, 1)
                                                    }
                                        except Exception:
                                            pass

                                if best_lap_data:
                                    all_results.append(best_lap_data)

                                progress_bar.progress((d_idx + 1) / total_drivers)
                            progress_bar.empty()

                        if all_results:
                            df_trac = pd.DataFrame(all_results)

                            # Ordina la tabella dal miglior valore di trazione al peggiore
                            df_trac = df_trac.sort_values(by='Dist to 100% Thr. (m)').reset_index(drop=True)

                            titolo_tab = "Migliore Assoluta" if analisi_mode == "Miglior Valore (Entro 1.5s dal Best)" else "Giro Selezionato"
                            st.markdown(f"#### 🔎 Confronto Trazione ({titolo_tab}) - Curva {sel_corner}")


                            def highlight_best_traction(s):
                                is_min = s == s.min()
                                return ['color: #00d2be; font-weight: bold;' if v else '' for v in is_min]


                            styled_c = df_trac.style.set_properties(**{
                                'background-color': '#1a1a1a',
                                'color': '#cccccc',
                                'border-color': '#333333',
                                'text-align': 'center'
                            }).apply(highlight_best_traction, subset=['Dist to 100% Thr. (m)'])

                            st.dataframe(styled_c, use_container_width=True, hide_index=True)

                            dl_filename = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                            sel_session_display, f"TRACTION_T{sel_corner}", sel_drivers)
                            img_buf = create_image_from_df(df_trac, f"Traction Analysis - T{sel_corner}")
                            st.download_button(
                                label="📸 Scarica Tabella come Immagine",
                                data=img_buf,
                                file_name=dl_filename,
                                mime="image/png"
                            )

                            st.info(
                                "💡 **Min Speed:** La velocità minima registrata dal pilota a centro curva.\n\n"
                                "💡 **Min Gear:** La marcia minima inserita.\n\n"
                                "💡 **Dist to 100% Thr. (m):** Quanti metri impiega il pilota, partendo dal punto di velocità minima, per tornare a schiacciare il pedale dell'acceleratore fino in fondo. Un valore più **basso** (evidenziato in azzurro) significa che l'auto ha una trazione migliore e il pilota si fida prima ad andare 'a tavoletta'.")
                        else:
                            st.warning(
                                "Dati telemetrici incompleti per effettuare l'analisi della trazione su questi giri.")
# ==============================================================================
# TOOL 8: SPEED
# ==============================================================================
elif tool == "SPEED":
    st.subheader("🏎️ TOP SPEED ANALYSIS")
    st.markdown("Velocità massime registrate nel corso dei giri selezionati sui principali rettilinei del tracciato.")

    col_sel, col_tab = st.columns([1.5, 4])
    selected_laps_to_analyze = []

    with col_sel:
        st.markdown(
            "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>SELEZIONA GIRO</b></div>",
            unsafe_allow_html=True)
        st.write("")

        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
            if not d_laps.empty:
                fastest_idx = d_laps['LapTimeSec'].idxmin()
                best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                col_drv = custom_colors.get(driver, "#FFF")

                opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                def_opt_idx = next((i for i, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>", unsafe_allow_html=True)
                sel_lap_info = st.selectbox(
                    f"Giro per {driver}",
                    opts,
                    index=def_opt_idx,
                    format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                    key=f"speed_lap_{driver}",
                    label_visibility="collapsed"
                )
                st.write("")

                target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                selected_laps_to_analyze.append({
                    'Driver': driver,
                    'Lap': int(sel_lap_info[0]),
                    'LapTime': sel_lap_info[1],
                    'lap_obj': target_lap
                })

    with col_tab:
        if selected_laps_to_analyze:
            with st.spinner("Estrazione dati telemetrici e ricerca velocità massime (cercando i picchi / peaks)..."):
                try:
                    circuit_info = session.get_circuit_info()
                    corners = circuit_info.corners
                    if 'Number' in corners.columns and 'Distance' in corners.columns:
                        corners = corners.dropna(subset=['Distance'])
                    else:
                        corners = pd.DataFrame()
                except Exception:
                    corners = pd.DataFrame()

                all_results = []
                for item in selected_laps_to_analyze:
                    tel = get_telemetry_for_lap(item['lap_obj'])
                    if tel.empty or 'Speed' not in tel.columns:
                        continue

                    peaks_idx, _ = signal.find_peaks(tel['Speed'], distance=40, prominence=15)

                    if len(peaks_idx) == 0:
                        continue

                    row_data = {'Driver': item['Driver'], 'Lap': item['Lap']}

                    peak_distances = tel.loc[peaks_idx, 'Distance'].values
                    peak_speeds = tel.loc[peaks_idx, 'Speed'].values

                    if not corners.empty:
                        try:
                            dist_t1 = corners[corners['Number'] == 1]['Distance'].values[0]
                            dist_t4 = corners[corners['Number'] == 4]['Distance'].values[0]
                            dist_t11 = corners[corners['Number'] == 11]['Distance'].values[0]
                            dist_t14 = corners[corners['Number'] == 14]['Distance'].values[0]


                            def get_max_speed_before(target_dist, search_range=400):
                                valid_peaks = [s for d, s in zip(peak_distances, peak_speeds) if
                                               (target_dist - search_range) <= d <= target_dist]
                                return int(max(valid_peaks)) if valid_peaks else None


                            row_data['Main Straight (vs T1)'] = get_max_speed_before(dist_t1, search_range=800)
                            row_data['Straight T3-T4'] = get_max_speed_before(dist_t4, search_range=500)
                            row_data['Straight T10-T11'] = get_max_speed_before(dist_t11, search_range=600)
                            row_data['Straight T13-T14'] = get_max_speed_before(dist_t14, search_range=500)

                        except IndexError:
                            top_4_idx = np.argsort(peak_speeds)[-4:][::-1]
                            for i, idx in enumerate(top_4_idx):
                                row_data[f'Top Speed {i + 1} (km/h)'] = int(peak_speeds[idx])
                    else:
                        top_4_idx = np.argsort(peak_speeds)[-4:][::-1]
                        for i, idx in enumerate(top_4_idx):
                            row_data[f'Top Speed {i + 1} (km/h)'] = int(peak_speeds[idx])

                    row_data = {k: v for k, v in row_data.items() if v is not None}
                    if len(row_data) > 2:
                        all_results.append(row_data)

                if all_results:
                    df_speed = pd.DataFrame(all_results)


                    def highlight_max_speed(s):
                        if s.dtype in ['int64', 'float64'] and s.name not in ['Lap']:
                            is_max = s == s.max()
                            return ['color: #FF2800; font-weight: bold;' if v else '' for v in is_max]
                        return [''] * len(s)


                    styled_speed = df_speed.style.set_properties(**{
                        'background-color': '#1a1a1a',
                        'color': '#cccccc',
                        'border-color': '#333333',
                        'text-align': 'center'
                    }).apply(highlight_max_speed, axis=0)

                    st.markdown("#### 🏁 Singolo Giro (Top Speed per Settore/Rettilineo)")
                    st.dataframe(styled_speed, use_container_width=True, hide_index=True)

                    dl_filename = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                    sel_session_display, "SPEED", sel_drivers)
                    img_buf = create_image_from_df(df_speed, "Top Speed Analysis")
                    st.download_button(
                        label="📸 Scarica Tabella Singolo Giro",
                        data=img_buf,
                        file_name=dl_filename,
                        mime="image/png"
                    )
                else:
                    st.warning("Non è stato possibile calcolare le velocità di punta per i giri selezionati.")

            # --- NUOVA SEZIONE: MEDIA TOP SPEED (ENTRO 2S DAL BEST) ---
            st.markdown("---")
            st.markdown("#### 📊 Media Top Speed Assoluta (Giri Entro 2s dal Best)")

            avg_speed_results = []

            with st.spinner("Calcolo media velocità massime sui giri migliori..."):
                for driver in sel_drivers:
                    d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
                    if d_laps.empty:
                        continue

                    fastest_time = d_laps['LapTimeSec'].min()
                    # Filtriamo solo i giri push (entro i 2 secondi dal best)
                    valid_laps = d_laps[d_laps['LapTimeSec'] <= fastest_time + 2.0]

                    driver_top_speeds = []

                    for _, lap_row in valid_laps.iterrows():
                        try:
                            tel = get_telemetry_for_lap(lap_row)
                            if not tel.empty and 'Speed' in tel.columns:
                                # Troviamo la velocità massima assoluta di questo specifico giro
                                lap_max_speed = tel['Speed'].max()
                                driver_top_speeds.append(lap_max_speed)
                        except Exception:
                            pass

                    if driver_top_speeds:
                        avg_top_speed = sum(driver_top_speeds) / len(driver_top_speeds)
                        avg_speed_results.append({
                            'Driver': driver,
                            'Giri Analizzati': len(driver_top_speeds),
                            'Media Top Speed (km/h)': round(avg_top_speed, 1),
                            'Picco Assoluto (km/h)': round(max(driver_top_speeds), 1)
                        })

            if avg_speed_results:
                df_avg_speed = pd.DataFrame(avg_speed_results)
                df_avg_speed = df_avg_speed.sort_values(by='Media Top Speed (km/h)', ascending=False).reset_index(
                    drop=True)


                def highlight_best_avg(s):
                    is_max = s == s.max()
                    return ['color: #00d2be; font-weight: bold;' if v else '' for v in is_max]


                styled_avg_speed = df_avg_speed.style.set_properties(**{
                    'background-color': '#1a1a1a',
                    'color': '#cccccc',
                    'border-color': '#333333',
                    'text-align': 'center'
                }).apply(highlight_best_avg, subset=['Media Top Speed (km/h)', 'Picco Assoluto (km/h)'])

                st.dataframe(styled_avg_speed, use_container_width=True, hide_index=True)

                st.info(
                    "💡 **Media Top Speed:** È la media dei picchi velocistici di tutti i giri 'push'. Utile per capire chi fa più costantemente affidamento sulla potenza o su un assetto scarico, al netto dell'eventuale uso del DRS.")
            else:
                st.warning("Nessun dato valido trovato per calcolare la media delle velocità massime aggregate.")
# ==============================================================================
# TOOL 9: BEST SECTORS & IDEAL LAP
# ==============================================================================
elif tool == "BEST SECTORS":
    st.subheader("⏱️ BEST SECTORS & IDEAL LAP TIME")
    st.markdown(
        "Classifica dei migliori settori assoluti registrati nella sessione, e calcolo dell'Ideal Lap Time (la somma dei 3 migliori settori personali di ciascun pilota).")

    if laps.empty:
        st.warning("Nessun dato cronometrico disponibile.")
    else:
        with st.spinner("Calcolo dei best sectors e ideal laps per tutti i piloti..."):
            all_drivers = laps['Driver'].dropna().unique()

            s1_data, s2_data, s3_data = [], [], []
            ideal_data = []  # Nuova lista per l'Ideal Lap

            for driver in all_drivers:
                d_laps = laps[laps['Driver'] == driver]

                best_s1 = d_laps['Sector1TimeSec'].min()
                best_s2 = d_laps['Sector2TimeSec'].min()
                best_s3 = d_laps['Sector3TimeSec'].min()

                if pd.notna(best_s1): s1_data.append({'Driver': driver, 'Time': best_s1})
                if pd.notna(best_s2): s2_data.append({'Driver': driver, 'Time': best_s2})
                if pd.notna(best_s3): s3_data.append({'Driver': driver, 'Time': best_s3})

                # Calcolo Ideal Lap se il pilota ha tutti e 3 i settori validi
                if pd.notna(best_s1) and pd.notna(best_s2) and pd.notna(best_s3):
                    ideal_time = best_s1 + best_s2 + best_s3
                    ideal_data.append({
                        'Driver': driver,
                        'S1': best_s1,
                        'S2': best_s2,
                        'S3': best_s3,
                        'IdealTime': ideal_time
                    })

            df_s1 = pd.DataFrame(s1_data).sort_values(by='Time').reset_index(drop=True)
            df_s2 = pd.DataFrame(s2_data).sort_values(by='Time').reset_index(drop=True)
            df_s3 = pd.DataFrame(s3_data).sort_values(by='Time').reset_index(drop=True)

            col1, col2, col3 = st.columns(3)


            def format_sector_df(df):
                if df.empty: return df
                best_time = df.iloc[0]['Time']
                formatted_data = []
                for i, row in df.iterrows():
                    drv = row['Driver']
                    time = row['Time']
                    if i == 0:
                        gap_str = f"{time:.3f} s"
                    else:
                        gap = time - best_time
                        gap_str = f"+{gap:.3f} s"

                    formatted_data.append({
                        'Pos': i + 1,
                        'Driver': drv,
                        'Time / Gap': gap_str
                    })
                return pd.DataFrame(formatted_data)


            def style_best_sector(df):
                def highlight_first(s):
                    return ['color: #8A2BE2; font-weight: bold;' if v == 1 else '' for v in s]

                return df.style.set_properties(**{
                    'background-color': '#1a1a1a',
                    'color': '#cccccc',
                    'border-color': '#333333',
                    'text-align': 'center'
                }).apply(highlight_first, subset=['Pos'])


            df_s1_fmt = format_sector_df(df_s1) if not df_s1.empty else pd.DataFrame()
            df_s2_fmt = format_sector_df(df_s2) if not df_s2.empty else pd.DataFrame()
            df_s3_fmt = format_sector_df(df_s3) if not df_s3.empty else pd.DataFrame()

            with col1:
                st.markdown("<h4 style='text-align: center; color: #FF2800;'>SECTOR 1</h4>", unsafe_allow_html=True)
                if not df_s1_fmt.empty:
                    st.dataframe(style_best_sector(df_s1_fmt), use_container_width=True, hide_index=True)
                    dl_file_1 = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                  sel_session_display, "BEST_S1", [])
                    st.download_button("📸 Scarica S1", data=create_image_from_df(df_s1_fmt, "Best Sector 1"),
                                       file_name=dl_file_1, mime="image/png")
                else:
                    st.write("N/A")

            with col2:
                st.markdown("<h4 style='text-align: center; color: #ffd100;'>SECTOR 2</h4>", unsafe_allow_html=True)
                if not df_s2_fmt.empty:
                    st.dataframe(style_best_sector(df_s2_fmt), use_container_width=True, hide_index=True)
                    dl_file_2 = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                  sel_session_display, "BEST_S2", [])
                    st.download_button("📸 Scarica S2", data=create_image_from_df(df_s2_fmt, "Best Sector 2"),
                                       file_name=dl_file_2, mime="image/png")
                else:
                    st.write("N/A")

            with col3:
                st.markdown("<h4 style='text-align: center; color: #00d2be;'>SECTOR 3</h4>", unsafe_allow_html=True)
                if not df_s3_fmt.empty:
                    st.dataframe(style_best_sector(df_s3_fmt), use_container_width=True, hide_index=True)
                    dl_file_3 = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                  sel_session_display, "BEST_S3", [])
                    st.download_button("📸 Scarica S3", data=create_image_from_df(df_s3_fmt, "Best Sector 3"),
                                       file_name=dl_file_3, mime="image/png")
                else:
                    st.write("N/A")

            # --- TABELLA UNICA SCARICABILE (S1 + S2 + S3) ---
            st.markdown("---")
            st.markdown("<h4 style='text-align: center;'>📸 SCARICA TABELLA COMPLETA (S1 + S2 + S3)</h4>",
                        unsafe_allow_html=True)

            comb_cols = []
            if not df_s1_fmt.empty:
                comb_cols.append(df_s1_fmt.rename(columns={'Driver': 'S1 DRIVER', 'Time / Gap': 'S1 TIME/GAP'}))
            if not df_s2_fmt.empty:
                s2_df = df_s2_fmt[['Driver', 'Time / Gap']].rename(
                    columns={'Driver': 'S2 DRIVER', 'Time / Gap': 'S2 TIME/GAP'})
                comb_cols.append(s2_df)
            if not df_s3_fmt.empty:
                s3_df = df_s3_fmt[['Driver', 'Time / Gap']].rename(
                    columns={'Driver': 'S3 DRIVER', 'Time / Gap': 'S3 TIME/GAP'})
                comb_cols.append(s3_df)

            if comb_cols:
                df_combined = pd.concat(comb_cols, axis=1).fillna("")
                dl_filename_combined = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                         sel_session_display, "BEST_SECTORS_ALL", [])
                img_buf_combined = create_image_from_df(df_combined, "Best Sectors Combined Analysis")

                col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
                with col_btn2:
                    st.download_button(
                        label="🚀 SCARICA IMMAGINE TABELLA SETTORI",
                        data=img_buf_combined,
                        file_name=dl_filename_combined,
                        mime="image/png",
                        use_container_width=True
                    )

            # --- NUOVA SEZIONE: IDEAL LAP TIME ---
            if ideal_data:
                st.markdown("---")
                st.markdown("<h3 style='text-align: center; color: #ffffff;'>🏎️ IDEAL LAP TIME CLASSIFICATION</h3>",
                            unsafe_allow_html=True)
                st.markdown(
                    "Questa tabella somma i record personali di ciascun pilota nei 3 settori, calcolando il giro potenziale perfetto (Ideal Lap) e ordinando la griglia dal più veloce al più lento.")

                # Creazione dataframe e ordinamento per Ideal Time crescente
                df_ideal = pd.DataFrame(ideal_data).sort_values(by='IdealTime').reset_index(drop=True)
                best_overall_ideal = df_ideal.iloc[0]['IdealTime']

                fmt_ideal_list = []
                for i, row in df_ideal.iterrows():
                    drv = row['Driver']
                    tot = row['IdealTime']

                    # Formattazione minuti e secondi
                    m = int(tot // 60)
                    s = tot % 60
                    time_str = f"{m}:{s:06.3f}" if m > 0 else f"{s:.3f}"

                    if i == 0:
                        gap_str = time_str
                    else:
                        gap = tot - best_overall_ideal
                        gap_str = f"{time_str} (+{gap:.3f} s)"

                    fmt_ideal_list.append({
                        'Pos': i + 1,
                        'Driver': drv,
                        'Best S1': f"{row['S1']:.3f}",
                        'Best S2': f"{row['S2']:.3f}",
                        'Best S3': f"{row['S3']:.3f}",
                        'Ideal Lap Time': gap_str
                    })

                df_ideal_fmt = pd.DataFrame(fmt_ideal_list)

                # Stile per la tabella a schermo in Streamlit
                styled_ideal = df_ideal_fmt.style.set_properties(**{
                    'background-color': '#1a1a1a',
                    'color': '#cccccc',
                    'border-color': '#333333',
                    'text-align': 'center'
                }).apply(
                    style_best_sector.highlight_first if hasattr(style_best_sector, 'highlight_first') else lambda x: [
                        'color: #8A2BE2; font-weight: bold;' if v == 1 else '' for v in x], subset=['Pos'])

                st.dataframe(styled_ideal, use_container_width=True, hide_index=True)

                # Pulsante di Download HD usando la tua funzione (esporta in altissima risoluzione)
                dl_filename_ideal = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                      sel_session_display, "IDEAL_LAP_TIME", [])
                img_buf_ideal = create_image_from_df(df_ideal_fmt, "Ideal Lap Time Classification")

                col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                with col_b2:
                    st.download_button(
                        label="🏎️ SCARICA TABELLA IDEAL LAP (ALTA DEFINIZIONE)",
                        data=img_buf_ideal,
                        file_name=dl_filename_ideal,
                        mime="image/png",
                        use_container_width=True
                    )
# ==============================================================================
# TOOL 10: G_LONGITUDINAL
# ==============================================================================
elif tool == "G_LONGITUDINAL":
    st.subheader("🚀 ACCELERAZIONE LONGITUDINALE (Speed vs G-Force)")
    st.markdown("Analisi dell'accelerazione e decelerazione longitudinale in funzione della velocità.")

    col_sel, col_tab = st.columns([1.5, 4])
    selected_laps_to_analyze = []

    with col_sel:
        st.markdown(
            "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>SELEZIONA GIRO</b></div>",
            unsafe_allow_html=True)
        st.write("")

        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
            if not d_laps.empty:
                fastest_idx = d_laps['LapTimeSec'].idxmin()
                best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                col_drv = custom_colors.get(driver, "#FFF")

                opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                def_opt_idx = next((i for i, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>", unsafe_allow_html=True)
                sel_lap_info = st.selectbox(
                    f"Giro per {driver}",
                    opts,
                    index=def_opt_idx,
                    format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                    key=f"along_lap_{driver}",
                    label_visibility="collapsed"
                )
                st.write("")

                target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                selected_laps_to_analyze.append({
                    'Driver': driver,
                    'Lap': int(sel_lap_info[0]),
                    'LapTime': sel_lap_info[1],
                    'lap_obj': target_lap,
                    'color': col_drv
                })

    with col_tab:
        if selected_laps_to_analyze:
            with st.spinner("Calcolo accelerazione longitudinale..."):
                fig = go.Figure()
                summary_data = []

                for item in selected_laps_to_analyze:
                    tel = get_telemetry_for_lap(item['lap_obj'])
                    if not tel.empty and 'Speed' in tel.columns and 'Acc_Smooth' in tel.columns:
                        g_force = tel['Acc_Smooth'] / 9.81

                        fig.add_trace(go.Scatter(
                            x=tel['Speed'],
                            y=g_force,
                            mode='markers',
                            marker=dict(size=4, color=item['color'], opacity=0.7),
                            name=f"{item['Driver']} L{item['Lap']}"
                        ))

                        pos_g = g_force[g_force > 0]
                        neg_g = g_force[g_force < 0]

                        max_trac = np.percentile(pos_g, 95) if len(pos_g) > 0 else np.nan
                        max_brake = np.percentile(neg_g, 5) if len(neg_g) > 0 else np.nan
                        mean_trac = pos_g.mean() if len(pos_g) > 0 else np.nan

                        summary_data.append({
                            'Driver': item['Driver'],
                            'Lap': item['Lap'],
                            'Max Traction (+G)': round(max_trac, 2) if pd.notna(max_trac) else None,
                            'Mean Traction (+G)': round(mean_trac, 2) if pd.notna(mean_trac) else None,
                            'Max Braking (-G)': round(max_brake, 2) if pd.notna(max_brake) else None
                        })

                if len(fig.data) > 0:
                    fig.update_layout(
                        title=get_chart_title("Accelerazione Longitudinale"),
                        images=get_watermark(),
                        template="plotly_dark",
                        paper_bgcolor='#0f0f0f',
                        plot_bgcolor='#0f0f0f',
                        xaxis_title="Velocità (km/h)",
                        yaxis_title="Accelerazione Longitudinale (G)",
                        height=550,
                        hovermode="closest",
                        legend=dict(orientation="h", y=1.02, x=0, xanchor="left", yanchor="bottom")
                    )
                    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)

                    st.plotly_chart(fig, use_container_width=True)

                    if summary_data:
                        df_summary = pd.DataFrame(summary_data)
                        st.markdown("#### 📊 Sintesi Prestazioni Longitudinali")


                        def highlight_max_trac(s):
                            is_max = s == s.max()
                            return ['color: #FF2800; font-weight: bold;' if v else '' for v in is_max]


                        def highlight_max_brake(s):
                            is_min = s == s.min()
                            return ['color: #00d2be; font-weight: bold;' if v else '' for v in is_min]


                        styled_summary = df_summary.style.set_properties(**{
                            'background-color': '#1a1a1a',
                            'color': '#cccccc',
                            'border-color': '#333333',
                            'text-align': 'center'
                        }).apply(highlight_max_trac, subset=['Max Traction (+G)']) \
                            .apply(highlight_max_brake, subset=['Max Braking (-G)'])

                        st.dataframe(styled_summary, use_container_width=True, hide_index=True)

                        dl_filename = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                        sel_session_display, "GLONG_SUMMARY", sel_drivers)
                        img_buf = create_image_from_df(df_summary, "Longitudinal G Summary")
                        st.download_button(
                            label="📸 Scarica Sintesi come Immagine",
                            data=img_buf,
                            file_name=dl_filename,
                            mime="image/png"
                        )

                    st.info(
                        "💡 **Cosa significa questo grafico?**\n\n"
                        "Questo scatter plot disegna l'inviluppo delle prestazioni longitudinali (trazione e staccata) rispetto alla velocità raggiunta.\n\n"
                        "🟢 **Valori POSITIVI (> 0 G): Fase di Accelerazione.** La parte alta del grafico mostra la capacità di spinta del motore e la trazione. I picchi massimi si trovano alle basse velocità (quando si usano le marce basse) e calano man mano che la velocità sale per via del Drag aerodinamico e dei rapporti del cambio più lunghi.\n\n"
                        "🔴 **Valori NEGATIVI (< 0 G): Fase di Frenata / Lift.** La parte bassa del grafico mostra la potenza decelerante dell'auto. A velocità elevate, l'enorme carico aerodinamico e la violenza dei freni permettono decelerazioni molto forti (spesso oltre -5 G). A basse velocità, la decelerazione massima ottenibile diminuisce perché manca il carico aerodinamico per schiacciare l'auto a terra, riducendo il grip meccanico sfruttabile."
                    )
                else:
                    st.warning("Dati telemetrici incompleti per tracciare il grafico.")

# ==============================================================================
# TOOL 11: GLATERAL
# ==============================================================================
elif tool == "GLATERAL":
    st.subheader("🏎️ GLATERAL: Grip Laterale vs Velocità")
    st.markdown("Analisi dell'efficienza aerodinamica e meccanica laterale in Forza G rispetto alla velocità.")

    col_sel, col_tab = st.columns([1.5, 4])
    selected_laps_to_analyze = []

    with col_sel:
        st.markdown(
            "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>SELEZIONA GIRO</b></div>",
            unsafe_allow_html=True)
        st.write("")
        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
            if not d_laps.empty:
                fastest_idx = d_laps['LapTimeSec'].idxmin()
                best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                col_drv = custom_colors.get(driver, "#FFF")
                opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                def_opt_idx = next((i for i, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>", unsafe_allow_html=True)
                sel_lap_info = st.selectbox(f"Giro {driver}", opts, index=def_opt_idx,
                                            format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                                            key=f"lat_lap_{driver}", label_visibility="collapsed")

                target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                selected_laps_to_analyze.append(
                    {'Driver': driver, 'Lap': int(sel_lap_info[0]), 'lap_obj': target_lap, 'color': col_drv})

    with col_tab:
        if selected_laps_to_analyze:
            with st.spinner("Calcolo dinamica laterale dai dati GPS e velocità..."):
                fig = go.Figure()
                summary_lat = []

                for item in selected_laps_to_analyze:
                    # Carichiamo la telemetria grezza per avere X e Y ad alta frequenza
                    tel = item['lap_obj'].get_telemetry()
                    if not tel.empty and 'X' in tel.columns:
                        # 1. Calcoliamo la variazione di direzione (heading) dalle coordinate GPS
                        v_ms = tel['Speed'] / 3.6
                        dx = tel['X'].diff().fillna(0)
                        dy = tel['Y'].diff().fillna(0)
                        dt = tel['Time'].dt.total_seconds().diff().fillna(0.1)

                        # Angolo di direzione in radianti
                        theta = np.arctan2(dy, dx)

                        # Svolgiamo l'angolo per evitare salti tra -pi e pi e calcoliamo lo Yaw Rate (omega)
                        d_theta = np.unwrap(theta)
                        yaw_rate = np.gradient(d_theta, dt)

                        # 2. Accelerazione laterale: a = v * omega
                        lat_acc_ms2 = v_ms * yaw_rate

                        # 3. Conversione in G con smoothing cinematico per mitigare il rumore GPS
                        # Filtro fisico: valori > 7.5G sono solitamente glitch strumentali
                        g_lat_series = (lat_acc_ms2 / 9.81).rolling(window=12, center=True).mean().abs()
                        g_lat_series[g_lat_series > 7.5] = np.nan

                        fig.add_trace(go.Scatter(
                            x=tel['Speed'],
                            y=g_lat_series,
                            mode='markers',
                            marker=dict(size=4, color=item['color'], opacity=0.5),
                            name=f"{item['Driver']} L{item['Lap']}"
                        ))

                        # KPI: Picco di G laterali (95° percentile per scartare il rumore residuo)
                        peak_lat_g = g_lat_series.dropna().quantile(0.95)
                        summary_lat.append(
                            {'Driver': item['Driver'], 'Lap': item['Lap'], 'Max Lateral G': round(peak_lat_g, 2)})

                fig.update_layout(
                    title=get_chart_title("Lateral G-Force"),
                    images=get_watermark(),
                    template="plotly_dark",
                    paper_bgcolor='#0f0f0f',
                    plot_bgcolor='#0f0f0f',
                    xaxis_title="Velocità (km/h)",
                    yaxis_title="Lateral G-Force",
                    height=550,
                    hovermode="closest",
                    legend=dict(orientation="h", y=1.02, x=0, xanchor="left", yanchor="bottom")
                )
                fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
                st.plotly_chart(fig, use_container_width=True)

                if summary_lat:
                    df_lat = pd.DataFrame(summary_lat)
                    st.markdown("#### 📊 Sintesi Performance Laterali")


                    def highlight_max_lat(s):
                        is_max = s == s.max()
                        return ['color: #00d2be; font-weight: bold;' if v else '' for v in is_max]


                    styled_lat = df_lat.style.set_properties(**{
                        'background-color': '#1a1a1a',
                        'color': '#cccccc',
                        'border-color': '#333333',
                        'text-align': 'center'
                    }).apply(highlight_max_lat, subset=['Max Lateral G'])

                    st.dataframe(styled_lat, use_container_width=True, hide_index=True)

                    dl_fn = generate_filename(sel_year, event_name_for_api, is_test, test_number, sel_session_display,
                                              "GLATERAL", sel_drivers)
                    img_buf = create_image_from_df(df_lat, "Lateral G Summary")
                    st.download_button(
                        label="📸 Scarica Sintesi come Immagine",
                        data=img_buf,
                        file_name=dl_fn,
                        mime="image/png"
                    )

                st.info(
                    "💡 **G Laterali:** Questo grafico mostra l'inviluppo del grip laterale rispetto alla velocità. "
                    "Nelle zone ad alta velocità (>200 km/h), valori di G più alti indicano una maggiore efficienza aerodinamica. "
                    "Nelle zone a bassa velocità (<120 km/h), indicano un miglior grip meccanico e precisione dell'avantreno.")

# ==============================================================================
# TOOL 12: CIRCLE (GG-Diagram - Friction Half-Circle)
# ==============================================================================
elif tool == "CIRCLE":
    st.subheader("⭕ CIRCLE: Mezzo Cerchio di Aderenza (GG-Diagram)")
    st.markdown(
        "Visualizzazione della combinazione tra forze laterali e longitudinali. I G laterali sono in **valore assoluto**, unificando le curve a destra e a sinistra per evidenziare chiaramente i limiti fisici della vettura (Cornering, Frenata, Trazione).")

    col_sel, col_plot = st.columns([1.5, 4])

    with col_sel:
        st.markdown(
            "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>IMPOSTAZIONI</b></div>",
            unsafe_allow_html=True)
        st.write("")

        analisi_mode = st.radio("Modalità di Analisi",
                                ["Singolo Giro (Selezionato)", "Tutti i giri (Entro 2s dal Best)"],
                                help="Scegli se analizzare un giro specifico o aggregare i dati di tutti i giri 'push' veri della sessione.")
        st.markdown("---")

        selected_laps_circle = []

        if analisi_mode == "Singolo Giro (Selezionato)":
            for driver in sel_drivers:
                d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
                if not d_laps.empty:
                    fastest_idx = d_laps['LapTimeSec'].idxmin()
                    best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                    col_drv = custom_colors.get(driver, "#FFF")
                    opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                    def_opt_idx = next((i for i, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                    st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>",
                                unsafe_allow_html=True)
                    sel_lap_info = st.selectbox(f"Giro {driver}", opts, index=def_opt_idx,
                                                format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                                                key=f"circle_lap_{driver}", label_visibility="collapsed")

                    target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                    selected_laps_circle.append(
                        {'Driver': driver, 'Lap': str(int(sel_lap_info[0])), 'lap_obj': [target_lap], 'color': col_drv})
        else:
            st.info(
                "⚡ **Analisi Aggregata:** Verranno uniti i dati di tutti i giri con un distacco massimo di 2.0s dal record personale.")
            for driver in sel_drivers:
                d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
                if not d_laps.empty:
                    fastest_time = d_laps['LapTimeSec'].min()
                    valid_laps = d_laps[d_laps['LapTimeSec'] <= fastest_time + 2.0]
                    col_drv = custom_colors.get(driver, "#FFF")
                    laps_list = [row for _, row in valid_laps.iterrows()]
                    selected_laps_circle.append(
                        {'Driver': driver, 'Lap': f"All Push ({len(laps_list)})", 'lap_obj': laps_list,
                         'color': col_drv})

        st.markdown("---")
        show_heatmap = st.checkbox("🔥 Mostra Mappa di Densità", value=False)
        show_envelope = st.checkbox("📐 Mostra Perimetro (Envelope Filtrato)", value=True)

    with col_plot:
        if selected_laps_circle:
            with st.spinner("Calcolo diagramma G-G e aggregazione dati..."):
                fig_gg = go.Figure()
                summary_circle = []

                all_g_lat_global = []
                all_g_long_global = []

                total_drivers = len(selected_laps_circle)
                progress_bar = st.progress(0)

                for d_idx, item in enumerate(selected_laps_circle):
                    driver_clean_g_lat = []
                    driver_clean_g_long = []

                    for lap_obj in item['lap_obj']:
                        try:
                            tel = get_telemetry_for_lap(lap_obj)
                            if not tel.empty and 'X' in tel.columns:
                                time_sec = tel['Time'].dt.total_seconds()
                                dt = time_sec.diff().fillna(0.1)

                                if 'Acc_Smooth' in tel.columns:
                                    g_long = tel['Acc_Smooth'] / 9.81
                                else:
                                    g_long = (tel['Speed'] / 3.6).diff().fillna(0) / dt / 9.81

                                v_ms = tel['Speed'] / 3.6

                                # --- MODIFICA 1: Pre-smoothing delle coordinate X e Y ---
                                smooth_x = tel['X'].rolling(window=5, center=True, min_periods=1).mean()
                                smooth_y = tel['Y'].rolling(window=5, center=True, min_periods=1).mean()

                                dx = smooth_x.diff().fillna(0)
                                dy = smooth_y.diff().fillna(0)
                                theta = np.arctan2(dy, dx)
                                d_theta = np.unwrap(theta)
                                yaw_rate = pd.Series(d_theta).diff().fillna(0) / dt
                                lat_acc_ms2 = v_ms * yaw_rate

                                # --- MODIFICA 2: Filtro Mediano + Media Mobile per rimuovere i picchi finti ---
                                g_lat_raw = lat_acc_ms2 / 9.81
                                # Il filtro mediano rimuove gli spikes anomali, la media liscia la curva
                                g_lat = g_lat_raw.rolling(window=5, center=True, min_periods=1).median()
                                g_lat = g_lat.rolling(window=15, center=True, min_periods=1).mean().fillna(0)

                                # --- MODIFICA 3: Maschera basata su limiti fisici reali (Max ~5.8G) ---
                                mask = (g_lat.abs() <= 5.8) & (g_long.abs() <= 6.0)

                                driver_clean_g_lat.extend(g_lat[mask].abs().tolist())
                                driver_clean_g_long.extend(g_long[mask].tolist())
                        except Exception:
                            pass

                    if driver_clean_g_lat and driver_clean_g_long:
                        lat_arr = np.array(driver_clean_g_lat)
                        long_arr = np.array(driver_clean_g_long)
                        marker_opacity = 0.4 if analisi_mode == "Singolo Giro (Selezionato)" else 0.15

                        fig_gg.add_trace(go.Scatter(
                            x=lat_arr, y=long_arr, mode='markers',
                            marker=dict(size=4, color=item['color'], opacity=marker_opacity, line=dict(width=0)),
                            name=f"{item['Driver']} {item['Lap']}"
                        ))

                        # --- LOGICA FILTRO OUTLIER (Rimozione Percentili) ---
                        points = np.column_stack((lat_arr, long_arr))
                        points = points[~np.isnan(points).any(axis=1)]

                        if len(points) > 3:
                            # Utilizziamo tutti i punti puliti dal filtro mediano, senza tagli percentili
                            filtered_points = points

                            if len(filtered_points) > 3:
                                if show_envelope:
                                    from scipy.spatial import ConvexHull

                                    hull = ConvexHull(filtered_points)
                                    hull_points = filtered_points[hull.vertices]
                                    hull_points = np.vstack((hull_points, hull_points[0]))
                                    fig_gg.add_trace(go.Scatter(
                                        x=hull_points[:, 0], y=hull_points[:, 1], mode='lines',
                                        line=dict(color=item['color'], width=2.5), showlegend=False, hoverinfo='skip'
                                    ))

                                # KPI estratti dai punti (i confini reali del poligono basati su tutti i dati puliti)
                                summary_circle.append({
                                    'Driver': item['Driver'],
                                    'Max Traction (+G)': round(np.max(filtered_points[:, 1]), 2),
                                    'Max Cornering (G)': round(np.max(filtered_points[:, 0]), 2),
                                    'Max Braking (-G)': round(abs(np.min(filtered_points[:, 1])), 2)
                                })

                        all_g_lat_global.extend(lat_arr.tolist())
                        all_g_long_global.extend(long_arr.tolist())

                    progress_bar.progress((d_idx + 1) / total_drivers)
                progress_bar.empty()

                if show_heatmap and all_g_lat_global and all_g_long_global:
                    fig_gg.add_trace(go.Histogram2dContour(
                        x=all_g_lat_global, y=all_g_long_global, colorscale='Inferno',
                        showscale=False, ncontours=15, line=dict(width=0), opacity=0.3, hoverinfo='skip'
                    ))

                # --- MODIFICA 4: Range grafico adattato ai nuovi limiti realistici ---
                fig_gg.update_layout(
                    title=get_chart_title("Friction Circle (GG-Diagram)"),
                    images=get_watermark(),
                    template="plotly_dark", paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f',
                    xaxis=dict(title="Lateral G (Valore Assoluto)", range=[0, 6], zeroline=True, zerolinecolor='#666',
                               gridcolor='#222'),
                    yaxis=dict(title="Longitudinal G (Accel/Freno)", range=[-6, 6], zeroline=True, zerolinecolor='#666',
                               scaleanchor="x", scaleratio=1, gridcolor='#222'),
                    width=700, height=700, margin=dict(l=40, r=40, t=40, b=40),
                    legend=dict(orientation="h", y=1.05, x=0),
                    annotations=[
                        dict(xref="paper", yref="paper", x=0.02, y=0.98, text="<b>⬆️ TRAZIONE</b>", showarrow=False,
                             font=dict(color="#ffffff", size=14, family="Anton"), xanchor="left", yanchor="top"),
                        dict(xref="paper", yref="paper", x=0.02, y=0.02, text="<b>⬇️ FRENATA</b>", showarrow=False,
                             font=dict(color="#ffffff", size=14, family="Anton"), xanchor="left", yanchor="bottom"),
                        dict(xref="paper", yref="paper", x=0.98, y=0.5, text="<b>CORNERING ➡️</b>", showarrow=False,
                             font=dict(color="#ffffff", size=14, family="Anton"), xanchor="right", yanchor="middle")
                    ]
                )

                for r in [2, 4, 6]:
                    fig_gg.add_shape(type="circle", x0=-r, y0=-r, x1=r, y1=r,
                                     line=dict(color="rgba(255,255,255,0.15)", dash="dot"))

                st.plotly_chart(fig_gg, use_container_width=True, config={'displaylogo': False})

                if summary_circle:
                    df_c = pd.DataFrame(summary_circle)
                    # Classifica basata sul cornering (chi tie  ne più G in curva)
                    df_c = df_c.sort_values(by='Max Cornering (G)', ascending=False).reset_index(drop=True)

                    st.markdown("#### 📊 Limiti Fisici della Vettura (Dati Filtrati)")


                    def highlight_max_extreme(s):
                        is_max = s == s.max()
                        return ['color: #00d2be; font-weight: bold;' if v else '' for v in is_max]


                    styled_c = df_c.style.set_properties(**{
                        'background-color': '#1a1a1a', 'color': '#cccccc', 'border-color': '#333333',
                        'text-align': 'center'
                    }).apply(highlight_max_extreme,
                             subset=['Max Traction (+G)', 'Max Cornering (G)', 'Max Braking (-G)'])

                    st.dataframe(styled_c, use_container_width=True, hide_index=True)

                    try:
                        dl_fn = generate_filename(sel_year, event_name_for_api, is_test, test_number,
                                                  sel_session_display, "CIRCLE_LIMITS", sel_drivers)
                        st.download_button(label="📸 Scarica Sintesi",
                                           data=create_image_from_df(df_c, "GG-Limits Summary"),
                                           file_name=dl_fn, mime="image/png")
                    except Exception:
                        pass
# ==============================================================================
# TOOL 13: TIRE DEGRADATION & RACE PACE
# ==============================================================================
elif tool == "TIRE DEGRADATION":
    st.subheader("🛞 TIRE DEGRADATION (Analisi Passo e Usura)")
    st.markdown("Stima matematica del degrado degli pneumatici basata sull'innalzamento dei tempi sul giro durante i Long Run. Vengono esclusi in automatico giri lenti, Safety Car e pit-stop.")

    if laps.empty:
        st.warning("Nessun dato cronometrico disponibile.")
    else:
        # Impostazioni Filtro
        col1, col2 = st.columns(2)
        with col1:
            min_laps_stint = st.number_input("Lunghezza minima dello stint (Giri)", min_value=3, max_value=20, value=5, help="Ignora gli stint più corti di questo valore (es. giri da qualifica).")
        with col2:
            outlier_threshold = st.slider("Filtro Traffico/Errori (+ Secondi)", min_value=1.0, max_value=5.0, value=2.0, step=0.5, help="Scarta i giri che sono X secondi più lenti del giro più veloce dello stint.")

        st.markdown("---")

        with st.spinner("Calcolo delle curve di degrado..."):
            fig_deg = go.Figure()
            summary_deg = []

            for driver in sel_drivers:
                d_laps = laps[laps['Driver'] == driver]
                if d_laps.empty: continue

                # Assicuriamoci che ci sia la colonna Stint
                if 'Stint' not in d_laps.columns:
                    st.error("I dati sugli Stint non sono disponibili per questa sessione.")
                    break

                # Analizziamo ogni stint separatamente
                for stint_num in d_laps['Stint'].dropna().unique():
                    stint_laps = d_laps[d_laps['Stint'] == stint_num].copy()

                    # Filtro 1: Lunghezza minima dello stint
                    if len(stint_laps) < min_laps_stint: continue

                    compound = stint_laps['Compound'].iloc[0] if 'Compound' in stint_laps.columns else "Unknown"
                    color_compound = {"SOFT": "#da291c", "MEDIUM": "#ffd100", "HARD": "#f0f0f0", "INTERMEDIATE": "#43b02a", "WET": "#0067a5"}.get(str(compound).upper(), custom_colors.get(driver, "#FFF"))

                    # Filtro 2: Rimuovere In-Lap, Out-Lap e TrackStatus non verde
                    valid_laps = stint_laps[(stint_laps['PitOutTime'].isnull()) & (stint_laps['PitInTime'].isnull())]

                    # Filtro 3: Escludere giri anomali (Traffico, errori, VSC)
                    if not valid_laps.empty:
                        best_stint_lap = valid_laps['LapTimeSec'].min()
                        valid_laps = valid_laps[valid_laps['LapTimeSec'] <= best_stint_lap + outlier_threshold]

                    # Ricalcoliamo se dopo i filtri abbiamo ancora abbastanza giri
                    if len(valid_laps) >= min_laps_stint:
                        x_laps = valid_laps['LapNumber'].values
                        y_times = valid_laps['LapTimeSec'].values

                        # Regressione Lineare (Polinomio di grado 1)
                        slope, intercept = np.polyfit(x_laps, y_times, 1)
                        trendline = slope * x_laps + intercept

                        # Aggiunta punti Scatter (I tempi effettivi)
                        fig_deg.add_trace(go.Scatter(
                            x=x_laps, y=y_times,
                            mode='markers',
                            marker=dict(color=custom_colors.get(driver, "#FFF"), size=8, opacity=0.7, line=dict(width=1, color=color_compound)),
                            name=f"{driver} (S{int(stint_num)} - {compound})"
                        ))

                        # Aggiunta linea di tendenza (Degrado)
                        fig_deg.add_trace(go.Scatter(
                            x=x_laps, y=trendline,
                            mode='lines',
                            line=dict(color=custom_colors.get(driver, "#FFF"), width=3, dash='solid'),
                            showlegend=False,
                            hoverinfo='skip'
                        ))

                        # Salvataggio dati per la tabella
                        summary_deg.append({
                            'Driver': driver,
                            'Stint': int(stint_num),
                            'Compound': compound,
                            'Laps Analizzati': len(valid_laps),
                            'Avg Pace': f"{int(valid_laps['LapTimeSec'].mean() // 60)}:{valid_laps['LapTimeSec'].mean() % 60:06.3f}",
                            'Degradation (s/lap)': slope
                        })

            if summary_deg:
                # Setup Layout Grafico Plotly
                fig_deg.update_layout(
                    title=get_chart_title("Analisi Passo e Degrado (Trendline)"),
                    images=get_watermark(),
                    template="plotly_dark",
                    paper_bgcolor='#0f0f0f',
                    plot_bgcolor='#0f0f0f',
                    xaxis=dict(title="Numero di Giro", gridcolor='#222', zeroline=False),
                    yaxis=dict(title="Tempo sul Giro (Secondi)", gridcolor='#222', zeroline=False),
                    hovermode="x unified",
                    height=600,
                    margin=dict(l=40, r=40, t=50, b=40),
                    legend=dict(orientation="h", y=1.05, x=0)
                )

                st.plotly_chart(fig_deg, use_container_width=True)

                # Creazione Tabella Riassuntiva
                df_summary = pd.DataFrame(summary_deg)

                # Formattazione e Ordinamento
                df_summary = df_summary.sort_values(by='Degradation (s/lap)').reset_index(drop=True)


                def color_deg(val):
                    if isinstance(val, str): return ''
                    if val < 0.05:
                        return 'color: #00d2be; font-weight:bold;'  # Ottimo (Basso degrado)
                    elif val > 0.15:
                        return 'color: #FF2800; font-weight:bold;'  # Pessimo (Alto degrado)
                    return 'color: #eeb200;'  # Medio


                df_summary_fmt = df_summary.copy()
                df_summary_fmt['Degradation (s/lap)'] = df_summary_fmt['Degradation (s/lap)'].apply(lambda x: f"+{x:.3f} s" if x > 0 else f"{x:.3f} s")

                styled_deg = df_summary_fmt.style.set_properties(**{
                    'background-color': '#1a1a1a', 'color': '#cccccc', 'border-color': '#333333', 'text-align': 'center'
                }).map(lambda x: color_deg(float(x.replace('+', '').replace(' s', ''))), subset=['Degradation (s/lap)'])

                st.markdown("#### 📊 Sintesi Degrado (Classifica per minor consumo)")
                st.dataframe(styled_deg, use_container_width=True, hide_index=True)

                st.info("💡 **Come leggere il dato:** Se la Degradation è **+0.100 s**, significa che il pilota perde in media 1 decimo di secondo a ogni giro percorso a causa del consumo della gomma. Valori evidenziati in azzurro indicano una gestione eccellente (o un carico di carburante che si svuota compensando il degrado).")
            else:
                st.warning("Nessun Long Run valido trovato con i filtri attuali. Prova a diminuire i giri minimi o aumentare la tolleranza del filtro.")

# ==============================================================================
# TOOL 14: SIMULAZIONE PASSO GARA E TELEMETRIA MEDIA
# ==============================================================================
elif tool == "SIMULAZIONE PASSO GARA":
    st.subheader("⏱️ SIMULAZIONE PASSO GARA")
    st.markdown("Filtra i giri per finestra temporale della sessione e per tempo sul giro. In basso potrai calcolare la Telemetria Media dei giri filtrati.")

    if laps.empty:
        st.warning("Nessun dato cronometrico disponibile.")
    else:
        show_labels = st.checkbox("Mostra tempi sui pallini nello Scatter", value=True)
        selected_laps_data = {}

        st.markdown("#### 1. Filtri Globali per la Simulazione")

        max_sess_min = 120
        min_lap_time = 60.0
        max_lap_time = 150.0

        valid_timing_laps = laps.dropna(subset=['LapTimeSec', 'LapStartTime']).copy()
        if not valid_timing_laps.empty:
            valid_timing_laps['MinutoSessione'] = valid_timing_laps['LapStartTime'].dt.total_seconds() / 60
            max_sess_min = int(valid_timing_laps['MinutoSessione'].max()) + 1
            min_lap_time = float(valid_timing_laps['LapTimeSec'].min())
            max_lap_time = float(valid_timing_laps['LapTimeSec'].max())

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            time_window = st.slider("Finestra Temporale Sessione (Minuti)", 0, max_sess_min, (0, max_sess_min))
        with col_f2:
            lap_window = st.slider("Finestra Tempo sul Giro (Secondi)", min_lap_time, max_lap_time, (min_lap_time, min_lap_time + 5.0))

        st.markdown("#### 2. Selezione Giri")
        cols = st.columns(len(sel_drivers) if len(sel_drivers) > 0 else 1)

        for i, driver in enumerate(sel_drivers):
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec', 'LapStartTime']).copy()
            if d_laps.empty: continue

            d_laps['MinutoSessione'] = d_laps['LapStartTime'].dt.total_seconds() / 60

            filtered_laps = d_laps[
                (d_laps['MinutoSessione'] >= time_window[0]) &
                (d_laps['MinutoSessione'] <= time_window[1]) &
                (d_laps['LapTimeSec'] >= lap_window[0]) &
                (d_laps['LapTimeSec'] <= lap_window[1])
                ]

            lap_times_dict = dict(zip(filtered_laps['LapNumber'].astype(int), filtered_laps['LapTimeSec']))
            filtered_opts = filtered_laps['LapNumber'].astype(int).tolist()

            with cols[i % len(cols)]:
                with st.expander(f"⚙️ Giri {driver}", expanded=True):
                    st.markdown(f"<span style='color:{custom_colors.get(driver, '#FFF')}; font-weight:bold;'>{driver}</span>", unsafe_allow_html=True)
                    chosen_laps = st.multiselect(
                        f"Giri",
                        options=filtered_opts,
                        default=filtered_opts,
                        format_func=lambda x: f"L{x} - {lap_times_dict.get(x, 0):.3f}s",
                        key=f"sim_laps_{driver}",
                        label_visibility="collapsed"
                    )
                    if chosen_laps:
                        selected_laps_data[driver] = d_laps[d_laps['LapNumber'].isin(chosen_laps)]

        if selected_laps_data:
            st.markdown("---")
            avg_data = []
            compound_colors = {
                "SOFT": "#da291c", "MEDIUM": "#ffd100", "HARD": "#f0f0f0",
                "INTERMEDIATE": "#43b02a", "WET": "#0067a5", "UNKNOWN": "#888888"
            }

            for driver, df_driver in selected_laps_data.items():
                avg_time = df_driver['LapTimeSec'].mean()
                avg_data.append({
                    'Driver': driver,
                    'AvgTimeSec': avg_time,
                    'AvgTimeStr': f"{int(avg_time // 60)}:{avg_time % 60:06.3f}" if avg_time >= 60 else f"{avg_time:.3f}",
                    'Color': custom_colors.get(driver, '#FFF')
                })

            df_avg = pd.DataFrame(avg_data).sort_values('AvgTimeSec')

            fig_bar = go.Figure()
            for _, row in df_avg.iterrows():
                fig_bar.add_trace(go.Bar(
                    x=[row['Driver']],
                    y=[row['AvgTimeSec']],
                    marker_color=row['Color'],
                    text=row['AvgTimeStr'],
                    textposition='auto',
                    textfont=dict(color='white', family="Anton", size=14),
                    name=row['Driver']
                ))

            min_y = df_avg['AvgTimeSec'].min() - 0.5
            max_y = df_avg['AvgTimeSec'].max() + 0.5

            fig_bar.update_layout(
                title=get_chart_title("Passo Medio sui Giri Selezionati"),
                images=get_watermark(),
                template="plotly_dark",
                paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f',
                yaxis=dict(range=[min_y, max_y], title="Tempo Medio (s)", gridcolor='#222'),
                xaxis=dict(title="Pilota"),
                showlegend=False,
                height=400
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            st.markdown("---")

            fig_scatter = go.Figure()
            for driver, df_driver in selected_laps_data.items():
                df_drv_sorted = df_driver.sort_values('LapNumber').copy()
                df_drv_sorted['RelativeLap'] = np.arange(1, len(df_drv_sorted) + 1)
                df_drv_sorted['TimeText'] = df_drv_sorted['LapTimeSec'].apply(lambda x: f"{x:.1f}")

                drv_color = custom_colors.get(driver, '#FFF')
                marker_colors = df_drv_sorted['Compound'].fillna('UNKNOWN').apply(
                    lambda x: compound_colors.get(str(x).upper(), '#888888')
                ).tolist()

                plot_mode = 'lines+markers+text' if show_labels else 'lines+markers'

                fig_scatter.add_trace(go.Scatter(
                    x=df_drv_sorted['RelativeLap'],
                    y=df_drv_sorted['LapTimeSec'],
                    mode=plot_mode,
                    text=df_drv_sorted['TimeText'] if show_labels else None,
                    textposition='top center',
                    textfont=dict(size=10, color='#cccccc'),
                    line=dict(color=drv_color, width=2, dash='dot'),
                    marker=dict(color=marker_colors, size=12, line=dict(color=drv_color, width=2)),
                    name=driver,
                    hovertext=df_drv_sorted['Compound'],
                    customdata=df_drv_sorted['LapNumber'],
                    hovertemplate="<b>%{name}</b><br>Giro Reale: %{customdata}<br>Giro Rel: %{x}<br>Time: %{y:.3f} s<br>Tyre: %{hovertext}<extra></extra>"
                ))

            fig_scatter.update_layout(
                title=get_chart_title("Evoluzione Tempi (Giri allineati)"),
                images=get_watermark(),
                template="plotly_dark",
                paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f',
                xaxis=dict(title="Numero Giro (Relativo)", gridcolor='#222', tickmode='linear'),
                yaxis=dict(title="Tempo sul Giro (s)", gridcolor='#222'),
                legend=dict(orientation="h", y=1.05, x=0),
                hovermode="x unified",
                height=550
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            st.markdown("#### 📊 Recap Tabellare")
            recap_data = []
            for driver, df_driver in selected_laps_data.items():
                if df_driver.empty: continue
                avg_time = df_driver['LapTimeSec'].mean()
                best_time = df_driver['LapTimeSec'].min()
                recap_data.append({'Pilota': driver, 'Giri Analizzati': len(df_driver), 'Passo Medio': f"{int(avg_time // 60)}:{avg_time % 60:06.3f}" if avg_time >= 60 else f"{avg_time:.3f}", 'Miglior Giro': f"{int(best_time // 60)}:{best_time % 60:06.3f}" if best_time >= 60 else f"{best_time:.3f}", 'Mescole': ", ".join([str(c) for c in df_driver['Compound'].dropna().unique()])})
            st.dataframe(pd.DataFrame(recap_data).style.set_properties(**{'background-color': '#1a1a1a', 'color': '#cccccc'}), use_container_width=True, hide_index=True)

            # --- SEZIONE TELEMETRIA MEDIA SOTTO LA TABELLA ---
            st.markdown("---")
            st.markdown("### 📈 Telemetria Media dei Giri Selezionati")
            st.info("Calcola la media matematica esatta, metro per metro, di tutti i giri selezionati in alto.")
            sel_ch_avg = st.multiselect("Canali da mediare", ['Speed', 'Throttle', 'Brake', 'RPM', 'nGear', 'Acc_Smooth', 'PowerFactor'], default=['Speed', 'Throttle'], key="ch_sim_avg")

            if st.button("🧮 CALCOLA TELEMETRIA MEDIA", key="btn_avg_sim"):
                if sel_ch_avg:
                    with st.spinner("Allineamento telemetria e calcolo della media matematica..."):
                        avg_plot_data = []
                        for driver, df_driver in selected_laps_data.items():
                            all_telemetries = []
                            best_lap_idx = df_driver['LapTimeSec'].idxmin()
                            master_tel = get_telemetry_for_lap(df_driver.loc[best_lap_idx])

                            if not master_tel.empty:
                                master_dist = master_tel['Distance'].values

                                for _, row in df_driver.iterrows():
                                    tel = get_telemetry_for_lap(row)
                                    if not tel.empty:
                                        comp_dist = tel['Distance'].values
                                        _, unique_indices = np.unique(comp_dist, return_index=True)
                                        comp_dist_u = comp_dist[unique_indices]

                                        interp_channels = {}
                                        for ch in sel_ch_avg:
                                            if ch in tel.columns:
                                                interp_ch = np.interp(master_dist, comp_dist_u, tel[ch].values[unique_indices])
                                                interp_channels[ch] = interp_ch
                                        all_telemetries.append(interp_channels)

                                if all_telemetries:
                                    avg_channels = {}
                                    for ch in sel_ch_avg:
                                        mat = np.array([t[ch] for t in all_telemetries if ch in t])
                                        if mat.size > 0:
                                            if ch == 'nGear':
                                                avg_channels[ch] = np.round(np.mean(mat, axis=0))
                                            else:
                                                avg_channels[ch] = np.mean(mat, axis=0)

                                    avg_plot_data.append({
                                        'driver': driver, 'dist': master_dist, 'channels': avg_channels,
                                        'color': custom_colors.get(driver, '#FFF'), 'n_laps': len(all_telemetries)
                                    })

                        n_rows = len(sel_ch_avg)
                        if n_rows > 0 and avg_plot_data:
                            fig_avg = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)
                            for idx_ch, ch in enumerate(sel_ch_avg):
                                t_row = idx_ch + 1
                                for idx_item, item in enumerate(avg_plot_data):
                                    if ch in item['channels']:
                                        label_name = f"{item['driver']} (Media {item['n_laps']} giri)"
                                        fig_avg.add_trace(go.Scatter(
                                            x=item['dist'], y=item['channels'][ch], mode='lines',
                                            name=label_name, line=dict(color=item['color'], width=2.5),
                                            legendgroup=item['driver'], showlegend=(idx_ch == 0)
                                        ), row=t_row, col=1)

                                        if ch == 'Speed':
                                            peaks_idx, _ = signal.find_peaks(item['channels'][ch], distance=40, prominence=15)
                                            valleys_idx, _ = signal.find_peaks(-item['channels'][ch], distance=40, prominence=15)

                                            if len(peaks_idx) > 0:
                                                drv_peak_x = item['dist'][peaks_idx]
                                                drv_peak_y = item['channels'][ch][peaks_idx] + 8 + (idx_item * 14)
                                                drv_peak_txt = [f"{int(v)}" for v in item['channels'][ch][peaks_idx]]
                                                fig_avg.add_trace(go.Scatter(x=drv_peak_x, y=drv_peak_y, mode='text', text=drv_peak_txt, textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color=item['color'], size=11, family="Roboto Mono")), row=t_row, col=1)

                                            if len(valleys_idx) > 0:
                                                drv_valley_x = item['dist'][valleys_idx]
                                                drv_valley_y = item['channels'][ch][valleys_idx] - 8 - (idx_item * 14)
                                                drv_valley_txt = [f"{int(v)}" for v in item['channels'][ch][valleys_idx]]
                                                fig_avg.add_trace(go.Scatter(x=drv_valley_x, y=drv_valley_y, mode='text', text=drv_valley_txt, textposition='bottom center', showlegend=False, hoverinfo='skip', textfont=dict(color=item['color'], size=11, family="Roboto Mono")), row=t_row, col=1)

                                units = {'Speed': 'km/h', 'Throttle': '%', 'Brake': '%', 'RPM': 'rpm', 'nGear': 'Gear', 'Acc_Smooth': 'm/s2', 'PowerFactor': 'W/kg'}
                                fig_avg.update_yaxes(title_text=f"Avg {ch} [{units.get(ch, '')}]", row=t_row, col=1)

                            fig_avg.update_layout(
                                title=get_chart_title("Average Telemetry (Simulazione)"),
                                images=get_watermark(), height=250 * n_rows, template="plotly_dark",
                                paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f', margin=dict(r=20, t=70),
                                hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0)
                            )
                            st.plotly_chart(fig_avg, use_container_width=True)

# ==============================================================================
# TOOL 17: PASSO GARA E TELEMETRIA MEDIA
# ==============================================================================
elif tool == "PASSO GARA":
    st.subheader("🏎️ PASSO GARA (Analisi in Gara)")
    st.markdown("Vengono scartati automaticamente i giri di SC, VSC, Bandiera Rossa, l'ingresso/uscita dai box e il primo giro (L1).")

    if laps.empty:
        st.warning("Nessun dato cronometrico disponibile.")
    else:
        col_flags, col_radio = st.columns([1, 3])
        with col_flags:
            show_labels = st.checkbox("Mostra tempi sui pallini", value=True)

        stint_options = ["Tutta la gara"] + [f"Stint {i}" for i in range(1, 11)]
        with col_radio:
            selected_global_stint = st.radio("Seleziona Stint", options=stint_options, horizontal=True, key="pace_perf_stint_race")

        selected_laps_data = {}


        def is_lap_green(status_str):
            if not isinstance(status_str, str): return True
            for bad_status in ['4', '5', '6', '7']:
                if bad_status in status_str: return False
            return True


        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec', 'Stint']).copy()
            if d_laps.empty: continue

            if selected_global_stint != "Tutta la gara":
                target_stint_num = int(selected_global_stint.split(" ")[1])
                d_laps = d_laps[d_laps['Stint'] == target_stint_num]

            d_laps_clean = d_laps[(d_laps['PitOutTime'].isnull()) & (d_laps['PitInTime'].isnull()) & (d_laps['LapNumber'] > 1)].copy()
            if 'TrackStatus' in d_laps_clean.columns:
                green_mask = d_laps_clean['TrackStatus'].apply(is_lap_green)
                d_laps_clean = d_laps_clean[green_mask]

            if not d_laps_clean.empty:
                selected_laps_data[driver] = d_laps_clean

        if not selected_laps_data:
            st.warning(f"Nessun dato valido trovato per i piloti selezionati in {selected_global_stint}.")
        else:
            st.markdown("---")
            st.markdown("#### Analisi Passo Medio")

            avg_data = []
            compound_colors = {
                "SOFT": "#da291c", "MEDIUM": "#ffd100", "HARD": "#f0f0f0",
                "INTERMEDIATE": "#43b02a", "WET": "#0067a5", "UNKNOWN": "#888888"
            }

            for driver, df_driver in selected_laps_data.items():
                avg_time = df_driver['LapTimeSec'].mean()
                avg_data.append({
                    'Driver': driver,
                    'AvgTimeSec': avg_time,
                    'AvgTimeStr': f"{int(avg_time // 60)}:{avg_time % 60:06.3f}" if avg_time >= 60 else f"{avg_time:.3f}",
                    'Color': custom_colors.get(driver, '#FFF')
                })

            df_avg = pd.DataFrame(avg_data).sort_values('AvgTimeSec')

            fig_bar = go.Figure()
            for _, row in df_avg.iterrows():
                fig_bar.add_trace(go.Bar(
                    x=[row['Driver']],
                    y=[row['AvgTimeSec']],
                    marker_color=row['Color'],
                    text=row['AvgTimeStr'],
                    textposition='auto',
                    textfont=dict(color='white', family="Anton", size=14),
                    name=row['Driver']
                ))

            min_y = df_avg['AvgTimeSec'].min() - 0.5
            max_y = df_avg['AvgTimeSec'].max() + 0.5

            fig_bar.update_layout(
                title=get_chart_title(f"Passo Medio in Gara - {selected_global_stint}"),
                images=get_watermark(),
                template="plotly_dark",
                paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f',
                yaxis=dict(range=[min_y, max_y], title="Tempo Medio (s)", gridcolor='#222'),
                xaxis=dict(title="Pilota"),
                showlegend=False,
                height=400
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            st.markdown("---")
            st.markdown("#### Scatter Plot Evoluzione Gara")

            fig_scatter = go.Figure()

            for driver, df_driver in selected_laps_data.items():
                df_drv_sorted = df_driver.sort_values('LapNumber').copy()
                df_drv_sorted['TimeText'] = df_drv_sorted['LapTimeSec'].apply(lambda x: f"{x:.1f}")

                drv_color = custom_colors.get(driver, '#FFF')
                marker_colors = df_drv_sorted['Compound'].fillna('UNKNOWN').apply(
                    lambda x: compound_colors.get(str(x).upper(), '#888888')
                ).tolist()

                plot_mode = 'lines+markers+text' if show_labels else 'lines+markers'

                fig_scatter.add_trace(go.Scatter(
                    x=df_drv_sorted['LapNumber'],
                    y=df_drv_sorted['LapTimeSec'],
                    mode=plot_mode,
                    text=df_drv_sorted['TimeText'] if show_labels else None,
                    textposition='top center',
                    textfont=dict(size=10, color='#cccccc'),
                    line=dict(color=drv_color, width=2, dash='dot'),
                    marker=dict(color=marker_colors, size=12, line=dict(color=drv_color, width=2)),
                    name=driver,
                    hovertext=df_drv_sorted['Compound'],
                    hovertemplate="<b>%{name}</b><br>Lap: %{x}<br>Time: %{y:.3f} s<br>Tyre: %{hovertext}<extra></extra>"
                ))

            fig_scatter.update_layout(
                title=get_chart_title(f"Evoluzione Tempi - {selected_global_stint}"),
                images=get_watermark(),
                template="plotly_dark",
                paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f',
                xaxis=dict(title="Giro di Gara", gridcolor='#222'),
                yaxis=dict(title="Tempo sul Giro (s)", gridcolor='#222'),
                legend=dict(orientation="h", y=1.05, x=0),
                hovermode="x unified",
                height=550
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            st.markdown("#### 📊 Recap Tabellare")
            recap_data = []
            for driver, df_driver in selected_laps_data.items():
                if df_driver.empty: continue
                avg_time = df_driver['LapTimeSec'].mean()
                best_time = df_driver['LapTimeSec'].min()
                recap_data.append({'Pilota': driver, 'Giri Validi': len(df_driver), 'Passo Medio': f"{int(avg_time // 60)}:{avg_time % 60:06.3f}" if avg_time >= 60 else f"{avg_time:.3f}", 'Miglior Giro': f"{int(best_time // 60)}:{best_time % 60:06.3f}" if best_time >= 60 else f"{best_time:.3f}", 'Mescole': ", ".join([str(c) for c in df_driver['Compound'].dropna().unique()])})
            st.dataframe(pd.DataFrame(recap_data).style.set_properties(**{'background-color': '#1a1a1a', 'color': '#cccccc'}), use_container_width=True, hide_index=True)

            # --- SEZIONE TELEMETRIA MEDIA SOTTO LA TABELLA ---
            st.markdown("---")
            st.markdown("### 📈 Telemetria Media del Passo Gara")
            st.info("Calcola la media matematica, metro per metro, di tutti i giri filtrati per questo stint.")
            sel_ch_avg_race = st.multiselect("Canali da mediare", ['Speed', 'Throttle', 'Brake', 'RPM', 'nGear', 'Acc_Smooth', 'PowerFactor'], default=['Speed', 'Throttle'], key="ch_race_avg")

            if st.button("🧮 CALCOLA TELEMETRIA MEDIA", key="btn_avg_race"):
                if sel_ch_avg_race:
                    with st.spinner("Allineamento telemetria e calcolo della media matematica..."):
                        avg_plot_data = []
                        for driver, df_driver in selected_laps_data.items():
                            all_telemetries = []
                            best_lap_idx = df_driver['LapTimeSec'].idxmin()
                            master_tel = get_telemetry_for_lap(df_driver.loc[best_lap_idx])

                            if not master_tel.empty:
                                master_dist = master_tel['Distance'].values

                                for _, row in df_driver.iterrows():
                                    tel = get_telemetry_for_lap(row)
                                    if not tel.empty:
                                        comp_dist = tel['Distance'].values
                                        _, unique_indices = np.unique(comp_dist, return_index=True)
                                        comp_dist_u = comp_dist[unique_indices]

                                        interp_channels = {}
                                        for ch in sel_ch_avg_race:
                                            if ch in tel.columns:
                                                interp_ch = np.interp(master_dist, comp_dist_u, tel[ch].values[unique_indices])
                                                interp_channels[ch] = interp_ch
                                        all_telemetries.append(interp_channels)

                                if all_telemetries:
                                    avg_channels = {}
                                    for ch in sel_ch_avg_race:
                                        mat = np.array([t[ch] for t in all_telemetries if ch in t])
                                        if mat.size > 0:
                                            if ch == 'nGear':
                                                avg_channels[ch] = np.round(np.mean(mat, axis=0))
                                            else:
                                                avg_channels[ch] = np.mean(mat, axis=0)

                                    avg_plot_data.append({
                                        'driver': driver, 'dist': master_dist, 'channels': avg_channels,
                                        'color': custom_colors.get(driver, '#FFF'), 'n_laps': len(all_telemetries)
                                    })

                        n_rows = len(sel_ch_avg_race)
                        if n_rows > 0 and avg_plot_data:
                            fig_avg = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)
                            for idx_ch, ch in enumerate(sel_ch_avg_race):
                                t_row = idx_ch + 1
                                for idx_item, item in enumerate(avg_plot_data):
                                    if ch in item['channels']:
                                        label_name = f"{item['driver']} (Media {item['n_laps']} giri)"
                                        fig_avg.add_trace(go.Scatter(
                                            x=item['dist'], y=item['channels'][ch], mode='lines',
                                            name=label_name, line=dict(color=item['color'], width=2.5),
                                            legendgroup=item['driver'], showlegend=(idx_ch == 0)
                                        ), row=t_row, col=1)

                                        if ch == 'Speed':
                                            peaks_idx, _ = signal.find_peaks(item['channels'][ch], distance=40, prominence=15)
                                            valleys_idx, _ = signal.find_peaks(-item['channels'][ch], distance=40, prominence=15)

                                            if len(peaks_idx) > 0:
                                                drv_peak_x = item['dist'][peaks_idx]
                                                drv_peak_y = item['channels'][ch][peaks_idx] + 8 + (idx_item * 14)
                                                drv_peak_txt = [f"{int(v)}" for v in item['channels'][ch][peaks_idx]]
                                                fig_avg.add_trace(go.Scatter(x=drv_peak_x, y=drv_peak_y, mode='text', text=drv_peak_txt, textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color=item['color'], size=11, family="Roboto Mono")), row=t_row, col=1)

                                            if len(valleys_idx) > 0:
                                                drv_valley_x = item['dist'][valleys_idx]
                                                drv_valley_y = item['channels'][ch][valleys_idx] - 8 - (idx_item * 14)
                                                drv_valley_txt = [f"{int(v)}" for v in item['channels'][ch][valleys_idx]]
                                                fig_avg.add_trace(go.Scatter(x=drv_valley_x, y=drv_valley_y, mode='text', text=drv_valley_txt, textposition='bottom center', showlegend=False, hoverinfo='skip', textfont=dict(color=item['color'], size=11, family="Roboto Mono")), row=t_row, col=1)

                                units = {'Speed': 'km/h', 'Throttle': '%', 'Brake': '%', 'RPM': 'rpm', 'nGear': 'Gear', 'Acc_Smooth': 'm/s2', 'PowerFactor': 'W/kg'}
                                fig_avg.update_yaxes(title_text=f"Avg {ch} [{units.get(ch, '')}]", row=t_row, col=1)

                            fig_avg.update_layout(
                                title=get_chart_title(f"Average Telemetry ({selected_global_stint})"),
                                images=get_watermark(), height=250 * n_rows, template="plotly_dark",
                                paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f', margin=dict(r=20, t=70),
                                hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0)
                            )
                            st.plotly_chart(fig_avg, use_container_width=True)


# ==============================================================================
# TOOL 18: RACE TRACE
# ==============================================================================
elif tool == "RACE TRACE":
    st.subheader("📈 RACE TRACE (Delta Cumulativo)")
    st.markdown("Visualizza l'andamento della gara calcolando il vantaggio o ritardo accumulato rispetto a un tempo medio costante. I picchi verso il basso sono pit-stop o giri lenti.")

    if laps.empty:
        st.warning("Nessun dato cronometrico disponibile.")
    else:
        # Calcolo automatico di un tempo medio realistico basato sui piloti selezionati per evitare linee fuori asse
        valid_laps = laps[(laps['Driver'].isin(sel_drivers)) & (laps['PitOutTime'].isnull()) & (laps['PitInTime'].isnull())].dropna(subset=['LapTimeSec'])

        if not valid_laps.empty:
            # Taglio i giri sotto SC per trovare la mediana del vero "race pace"
            min_t = valid_laps['LapTimeSec'].min()
            clean_for_med = valid_laps[valid_laps['LapTimeSec'] < min_t * 1.15]
            default_ref = clean_for_med['LapTimeSec'].median() if not clean_for_med.empty else min_t + 2.0
        else:
            default_ref = 90.0

        col_cfg, _ = st.columns([1, 2])
        with col_cfg:
            ref_time = st.number_input("Tempo Costante di Riferimento (s)", min_value=50.0, max_value=300.0, value=float(round(default_ref, 2)), step=0.1, help="Ogni giro calcolerà il delta rispetto a questo tempo fisso e lo accumulerà al totale.")

        fig_trace = go.Figure()

        for driver in sel_drivers:
            d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec', 'LapNumber']).sort_values('LapNumber').copy()
            if d_laps.empty: continue

            # Delta cumulativo: (Tempo del pilota) - (Tempo di riferimento)
            # Se è positivo, ha girato più LENTO del riferimento
            d_laps['Delta'] = d_laps['LapTimeSec'] - ref_time
            d_laps['CumDelta'] = d_laps['Delta'].cumsum()

            fig_trace.add_trace(go.Scatter(
                x=d_laps['LapNumber'],
                y=d_laps['CumDelta'],
                mode='lines',
                line=dict(color=custom_colors.get(driver, '#FFF'), width=3),
                name=driver,
                hovertemplate="<b>%{name}</b><br>Lap: %{x}<br>Delta Cum: %{y:.2f} s<extra></extra>"
            ))

        fig_trace.update_layout(
            title=get_chart_title(f"Race Trace (Target Pace: {ref_time:.2f}s)"),
            images=get_watermark(),
            template="plotly_dark",
            paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f',
            xaxis=dict(title="Giro di Gara", gridcolor='#222'),
            yaxis=dict(title="Delta Cumulativo (s)", autorange="reversed", gridcolor='#222'),
            hovermode="x unified",
            height=600,
            legend=dict(orientation="h", y=1.05, x=0)
        )

        # Linea dello zero per indicare il passo perfetto
        fig_trace.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)

        st.plotly_chart(fig_trace, use_container_width=True)
        st.info("💡 **Come leggere il Race Trace:** Il grafico ha l'asse Y invertito per comodità visiva. Se la linea sale (verso l'alto), il pilota sta guadagnando tempo sul target impostato (è più veloce). Se la linea scende, sta perdendo terreno (es. usura gomme). I grossi cali verticali rappresentano i Pit-Stop o fasi di Safety Car.")


# ==============================================================================
# TOOL 15: TELEMETRY DIFF SESSION
# ==============================================================================
elif tool == "TELEMETRY DIFF SESSION":
    st.subheader("🔀 TELEMETRY DIFF SESSION (Cross-Year & Session Comparison)")
    st.markdown("Confronta la telemetria tra due sessioni differenti. La **Sessione A** è quella principale caricata nel menu laterale. Usa questo pannello per caricare la **Sessione B**.")

    if 'session_b_loaded' not in st.session_state:
        st.session_state['session_b_loaded'] = None
        st.session_state['session_b_info'] = ""

    col_sa, col_sb = st.columns(2)

    with col_sa:
        st.markdown("### 🏁 SESSIONE A (Riferimento)")
        if st.session_state['session_loaded']:
            st.success(f"✔️ Caricata: {sel_year} {sel_event_label} - {sel_session_display}")
        else:
            st.warning("Carica prima la Sessione A dalla barra laterale a sinistra.")

    with col_sb:
        st.markdown("### 🔍 SESSIONE B (Da confrontare)")

        with st.form("form_load_b"):
            diff_year = st.selectbox("Anno Sessione B", [2026, 2025, 2024, 2023], index=1)

            with st.spinner("Scaricando il calendario..."):
                schedule_b = get_schedule_data(diff_year)

            events_map_b = {}
            if not schedule_b.empty:
                test_cnt = 1
                test_evs = schedule_b[schedule_b['EventName'].str.contains("Test", case=False, na=False)]
                for _, r in test_evs.iterrows():
                    events_map_b[f"TEST: Bahrain {test_cnt}"] = r['EventName']
                    test_cnt += 1
                if diff_year == 2026 and len(test_evs) < 2:
                    events_map_b["TEST: Bahrain 1"] = "Pre-Season Testing 1"
                    events_map_b["TEST: Bahrain 2"] = "Pre-Season Testing 2"

                gps_b = schedule_b[(schedule_b['RoundNumber'] > 0) & (~schedule_b['EventName'].str.contains("Test", case=False, na=False))]
                for _, r in gps_b.iterrows():
                    events_map_b[f"R{r['RoundNumber']}: {r['EventName']}"] = r['EventName']

            diff_event_label = st.selectbox("Evento B", list(events_map_b.keys()) if events_map_b else ["N/A"])

            if events_map_b and diff_event_label != "N/A":
                ev_name_b = events_map_b[diff_event_label]
                is_test_b = "TEST:" in diff_event_label
                test_num_b = 1

                if is_test_b:
                    try:
                        test_num_b = int(diff_event_label.split()[-1])
                    except:
                        pass
                    opts_b = ['Day 1', 'Day 2', 'Day 3']
                else:
                    opts_b = []
                    try:
                        ev_row_b = schedule_b[schedule_b['EventName'] == ev_name_b].iloc[0]
                        for i in range(1, 6):
                            s_n = ev_row_b.get(f'Session{i}')
                            if pd.notna(s_n) and str(s_n).strip() not in ['', 'None']:
                                opts_b.append(str(s_n).strip())
                    except:
                        pass
                    if not opts_b:
                        opts_b = ['Practice 1', 'Practice 2', 'Practice 3', 'Qualifying', 'Race']

                diff_sess_display = st.selectbox("Sessione B", opts_b)

            submit_b = st.form_submit_button("🔌 CARICA SESSIONE B", type="primary")

        if submit_b and events_map_b and diff_event_label != "N/A":
            sess_id_b = 1 if diff_sess_display == 'Day 1' else (2 if diff_sess_display == 'Day 2' else (3 if diff_sess_display == 'Day 3' else diff_sess_display))

            with st.spinner("Connessione ai server F1 in corso per la Sessione B..."):
                sess_b_obj, err_b = load_session_data(diff_year, ev_name_b, sess_id_b, is_test_b, test_num_b)
                if sess_b_obj is not None:
                    st.session_state['session_b_loaded'] = sess_b_obj
                    st.session_state['session_b_info'] = f"{diff_year} {diff_event_label} - {diff_sess_display}"
                    st.success("✔️ Sessione B scaricata ed in memoria!")
                else:
                    st.session_state['session_b_loaded'] = None
                    st.session_state['session_b_info'] = ""
                    st.error(f"Errore caricamento: {err_b}")

        if st.session_state.get('session_b_loaded'):
            st.info(f"💾 In Memoria: **{st.session_state['session_b_info']}**")

    st.markdown("---")

    if st.session_state['session_loaded'] and st.session_state.get('session_b_loaded'):
        st.markdown("### 🏎️ SELEZIONE GIRI DA CONFRONTARE")

        col_laps_a, col_laps_b = st.columns(2)

        sess_a = st.session_state['session_loaded']
        sess_b = st.session_state['session_b_loaded']

        laps_a = process_laps(sess_a)
        laps_b = process_laps(sess_b)

        selected_laps_diff = {}

        with col_laps_a:
            st.markdown(f"**Piloti Sessione A ({sel_year})**")
            if not laps_a.empty:
                drv_a_avail = sorted(laps_a['Driver'].dropna().unique())
                sel_drv_a = st.multiselect("Scegli Piloti (Sess A)", drv_a_avail, default=drv_a_avail[:1] if drv_a_avail else [], key="diff_drv_a")

                for d in sel_drv_a:
                    d_laps = laps_a[laps_a['Driver'] == d].dropna(subset=['LapTimeSec'])
                    if not d_laps.empty:
                        best_idx = d_laps['LapTimeSec'].idxmin()
                        best_ln = d_laps.loc[best_idx, 'LapNumber']
                        opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                        def_opt = next((o for o in opts if o[0] == best_ln), None)

                        scelte = st.multiselect(
                            f"Giro {d} (Sess A)", opts, default=[def_opt] if def_opt else [],
                            format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s", key=f"diff_la_{d}"
                        )
                        for sc in scelte:
                            lap_row = d_laps[d_laps['LapNumber'] == sc[0]].iloc[0]
                            label = f"[{str(sel_year)[-2:]} A] {d} (L{int(sc[0])})"
                            selected_laps_diff[label] = {'lap': lap_row, 'color': custom_colors.get(d, '#FFFFFF'), 'time': sc[1], 'sess': 'A'}
            else:
                st.warning("Nessun giro valido in Sessione A")

        with col_laps_b:
            year_b_display = st.session_state['session_b_info'].split(" ")[0] if st.session_state['session_b_info'] else "B"
            st.markdown(f"**Piloti Sessione B ({year_b_display})**")

            if not laps_b.empty:
                drv_b_avail = sorted(laps_b['Driver'].dropna().unique())
                sel_drv_b = st.multiselect("Scegli Piloti (Sess B)", drv_b_avail, default=drv_b_avail[:1] if drv_b_avail else [], key="diff_drv_b")

                for d in sel_drv_b:
                    d_laps = laps_b[laps_b['Driver'] == d].dropna(subset=['LapTimeSec'])
                    if not d_laps.empty:
                        best_idx = d_laps['LapTimeSec'].idxmin()
                        best_ln = d_laps.loc[best_idx, 'LapNumber']
                        opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                        def_opt = next((o for o in opts if o[0] == best_ln), None)

                        scelte = st.multiselect(
                            f"Giro {d} (Sess B)", opts, default=[def_opt] if def_opt else [],
                            format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s", key=f"diff_lb_{d}"
                        )
                        for sc in scelte:
                            lap_row = d_laps[d_laps['LapNumber'] == sc[0]].iloc[0]
                            label = f"[{year_b_display[-2:]} B] {d} (L{int(sc[0])})"
                            selected_laps_diff[label] = {'lap': lap_row, 'color': DRIVER_COLORS.get(d, '#00d2be'), 'time': sc[1], 'sess': 'B'}
            else:
                st.warning("Nessun giro valido in Sessione B")

        st.markdown("---")
        st.markdown("### 📈 PLOT TELEMETRIA COMPARATA")

        sel_ch_diff = st.multiselect("Canali da visualizzare", ['Delta', 'Speed', 'Throttle', 'Brake', 'RPM', 'nGear'], default=['Delta', 'Speed', 'Throttle', 'Brake'], key="diff_ch")

        if selected_laps_diff:
            with st.spinner("Elaborazione Telemetria incrociata..."):
                ref_key = min(selected_laps_diff.keys(), key=lambda k: selected_laps_diff[k]['time'])
                ref_lap = selected_laps_diff[ref_key]['lap']
                ref_tel = get_telemetry_for_lap(ref_lap)

                if not ref_tel.empty:
                    ref_dist = ref_tel['Distance'].values
                    ref_time = ref_tel['Time'].dt.total_seconds().values

                    plot_data_diff = []
                    for label, info in selected_laps_diff.items():
                        comp_tel = get_telemetry_for_lap(info['lap'])
                        if not comp_tel.empty:
                            is_ref = (label == ref_key)

                            if is_ref:
                                delta_time = np.zeros(len(ref_dist))
                            else:
                                comp_dist = comp_tel['Distance'].values
                                comp_time = comp_tel['Time'].dt.total_seconds().values
                                _, unique_indices = np.unique(comp_dist, return_index=True)
                                comp_time_interp = np.interp(ref_dist, comp_dist[unique_indices], comp_time[unique_indices])
                                delta_time = comp_time_interp - ref_time

                            dash_style = 'solid' if info['sess'] == 'A' else 'dash'

                            plot_data_diff.append({
                                'label': f"{label} ({info['time']:.3f}s)",
                                'data': comp_tel,
                                'delta': delta_time,
                                'color': info['color'],
                                'is_ref': is_ref,
                                'dash': dash_style,
                                'line_width': 3 if is_ref else 2
                            })

                    show_delta_diff = 'Delta' in sel_ch_diff
                    ch_list_diff = [c for c in sel_ch_diff if c != 'Delta']
                    n_rows_diff = len(ch_list_diff) + (1 if show_delta_diff else 0)

                    if n_rows_diff > 0 and plot_data_diff:
                        fig_diff = make_subplots(rows=n_rows_diff, cols=1, shared_xaxes=True, vertical_spacing=0.05)
                        start_row_diff = 2 if show_delta_diff else 1

                        if show_delta_diff:
                            for item in plot_data_diff:
                                prefix = "Ref " if item['is_ref'] else ""
                                fig_diff.add_trace(go.Scatter(x=ref_dist, y=item['delta'], mode='lines', name=f"{prefix}{item['label']}", line=dict(color=item['color'], width=item['line_width'], dash=item['dash']), legendgroup=item['label'], showlegend=True), row=1, col=1)
                            fig_diff.update_yaxes(title_text="Delta (s)", row=1, col=1)
                            fig_diff.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3, row=1, col=1)

                        for idx, item in enumerate(plot_data_diff):
                            df_c = item['data']
                            for i, ch in enumerate(ch_list_diff):
                                t_row = i + start_row_diff
                                show_leg_diff = (not show_delta_diff) and (i == 0)
                                if ch in df_c.columns:
                                    prefix = "Ref " if item['is_ref'] else ""
                                    fig_diff.add_trace(go.Scatter(x=df_c['Distance'], y=df_c[ch], mode='lines', name=f"{prefix}{item['label']}", line=dict(color=item['color'], width=item['line_width'], dash=item['dash']), legendgroup=item['label'], showlegend=show_leg_diff), row=t_row, col=1)
                                    if idx == 0:
                                        units = {'Speed': 'km/h', 'Throttle': '%', 'Brake': '%', 'RPM': 'rpm', 'nGear': 'Gear'}
                                        fig_diff.update_yaxes(title_text=f"{ch} [{units.get(ch, '')}]", row=t_row, col=1)

                        fig_diff.update_layout(
                            title=get_chart_title("Telemetria Comparata Diff Session"),
                            images=get_watermark(),
                            height=250 * n_rows_diff,
                            template="plotly_dark", paper_bgcolor='#0f0f0f', plot_bgcolor='#0f0f0f', margin=dict(r=20, t=70), hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0))
                        st.plotly_chart(fig_diff, use_container_width=True)

                        st.info("💡 **Legenda Grafico:** Le linee **continue** rappresentano i dati della Sessione A (Base), mentre le linee **tratteggiate** indicano i dati della Sessione B (Confronto).")
        else:
            st.warning("Seleziona almeno un giro dalle Sessioni A o B per visualizzare il grafico.")

# ==============================================================================
# TOOL 16: MICROSECTORS MAP
# ==============================================================================
elif tool == "MICROSECTORS MAP":
    st.subheader("🗺️ MICROSECTORS DOMINANCE MAP")
    st.markdown("Confronta i piloti selezionati per scoprire chi è il più veloce in ogni microsettore del tracciato.")

    if len(sel_drivers) < 2:
        st.warning("Seleziona almeno 2 piloti dalla barra laterale per effettuare il confronto sui microsettori.")
    else:
        col_sel, col_plot = st.columns([1.5, 4])

        with col_sel:
            st.markdown(
                "<div style='background:#111; padding:10px; border-radius:5px; border-left:3px solid #FF2800;'><b>IMPOSTAZIONI</b></div>",
                unsafe_allow_html=True)
            st.write("")
            num_microsectors = st.slider("Numero di Microsettori", min_value=10, max_value=50, value=25, step=1)

            st.markdown("---")
            st.markdown("#### Selezione Giri")
            selected_laps_micro = {}

            cols_micro = st.columns(len(sel_drivers) if len(sel_drivers) > 0 else 1)

            for i, driver in enumerate(sel_drivers):
                d_laps = laps[laps['Driver'] == driver].dropna(subset=['LapTimeSec'])
                if not d_laps.empty:
                    fastest_idx = d_laps['LapTimeSec'].idxmin()
                    best_lap_num = d_laps.loc[fastest_idx, 'LapNumber']
                    col_drv = custom_colors.get(driver, "#FFF")

                    opts = d_laps[['LapNumber', 'LapTimeSec']].values.tolist()
                    def_opt_idx = next((j for j, opt in enumerate(opts) if opt[0] == best_lap_num), 0)

                    with cols_micro[i % len(cols_micro)]:
                        st.markdown(f"<span style='color:{col_drv}; font-weight:bold;'>{driver}</span>", unsafe_allow_html=True)
                        sel_lap_info = st.selectbox(
                            f"Giro per {driver}",
                            opts,
                            index=def_opt_idx,
                            format_func=lambda x: f"L{int(x[0])} - {x[1]:.3f}s",
                            key=f"micro_lap_{driver}",
                            label_visibility="collapsed"
                        )
                        st.write("")

                    target_lap = d_laps[d_laps['LapNumber'] == sel_lap_info[0]].iloc[0]
                    selected_laps_micro[driver] = {
                        'lap_obj': target_lap,
                        'color': col_drv,
                        'time': sel_lap_info[1]
                    }

        with col_plot:
            if len(selected_laps_micro) >= 2:
                with st.spinner("Suddivisione pista e calcolo tempi microsettori..."):

                    ref_driver = min(selected_laps_micro.keys(), key=lambda d: selected_laps_micro[d]['time'])
                    ref_lap = selected_laps_micro[ref_driver]['lap_obj']
                    ref_tel = get_telemetry_for_lap(ref_lap)

                    if not ref_tel.empty and 'Distance' in ref_tel.columns and 'X' in ref_tel.columns:
                        max_dist = ref_tel['Distance'].max()
                        bins = np.linspace(0, max_dist, num_microsectors + 1)

                        driver_sector_times = {}
                        for d, info in selected_laps_micro.items():
                            tel = get_telemetry_for_lap(info['lap_obj'])
                            if not tel.empty:
                                comp_dist = tel['Distance'].values
                                comp_time = tel['Time'].dt.total_seconds().values

                                _, unique_indices = np.unique(comp_dist, return_index=True)
                                interp_time = np.interp(bins, comp_dist[unique_indices], comp_time[unique_indices])

                                driver_sector_times[d] = np.diff(interp_time)

                        if driver_sector_times:
                            df_sectors = pd.DataFrame(driver_sector_times)
                            fastest_drivers = df_sectors.idxmin(axis=1)

                            fig_map = go.Figure()

                            ref_dist = ref_tel['Distance'].values
                            ref_x = ref_tel['X'].values
                            ref_y = ref_tel['Y'].values

                            bin_indices = np.digitize(ref_dist, bins)

                            added_legends = set()

                            for i in range(1, num_microsectors + 1):
                                mask = (bin_indices == i)

                                idx_true = np.where(mask)[0]
                                if len(idx_true) > 0:
                                    last_idx = idx_true[-1]
                                    if last_idx + 1 < len(mask):
                                        mask[last_idx + 1] = True

                                winner = fastest_drivers.iloc[i - 1]
                                w_color = selected_laps_micro[winner]['color']

                                show_leg = False
                                if winner not in added_legends:
                                    show_leg = True
                                    added_legends.add(winner)

                                fig_map.add_trace(go.Scatter(
                                    x=ref_x[mask],
                                    y=ref_y[mask],
                                    mode='lines',
                                    line=dict(color=w_color, width=8),
                                    name=winner,
                                    legendgroup=winner,
                                    showlegend=show_leg,
                                    hoverinfo='name'
                                ))

                            fig_map.update_layout(
                                title=get_chart_title(f"Microsectors Dominance Map ({num_microsectors} Sectors)"),
                                images=get_watermark(),
                                template="plotly_dark",
                                paper_bgcolor='#0f0f0f',
                                plot_bgcolor='#0f0f0f',
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
                                height=650,
                                margin=dict(l=0, r=0, t=70, b=0),
                                legend=dict(orientation="h", y=1.05, x=0)
                            )

                            st.plotly_chart(fig_map, use_container_width=True)

                            st.info("💡 **Come leggere la mappa:** Il tracciato è stato diviso in segmenti in base alla distanza. L'algoritmo calcola il tempo di percorrenza di ciascun pilota all'interno di quello specifico pezzo di pista e colora il tracciato col colore di chi è stato più rapido.")
