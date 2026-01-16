import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. KONFIGURATION & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; border-radius: 5px; font-weight: bold; }
    .stTable { background-color: #1a1c23; color: #00d4ff; border-radius: 10px; }
    div[data-baseweb="select"] > div { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    try:
        return st.connection("supabase", type=SupabaseConnection, 
                             url=st.secrets["connections"]["supabase"]["url"], 
                             key=st.secrets["connections"]["supabase"]["key"])
    except Exception as e:
        st.error(f"Verbindung zu Supabase fehlgeschlagen: {e}")
        return None

conn = init_connection()

# --- 3. ELO-LOGIK ---
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        new_a = round(rating_a + k * (1 - prob_a))
        new_b = round(rating_b + k * (0 - (1 - prob_a)))
    else:
        new_a = round(rating_a + k * (0 - prob_a))
        new_b = round(rating_b + k * (1 - (1 - prob_a)))
    return new_a, new_b

# --- 4. DATEN INITIAL LADEN ---
players = []
recent_matches = []
if conn:
    try:
        p_res = conn.table("profiles").select("*").execute()
        players = p_res.data or []
        m_res = conn.table("matches").select("*").order("created_at", desc=True).execute()
        recent_matches = m_res.data or []
    except Exception:
        pass

# --- 5. UI STRUKTUR ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("### Top Spieler")
        if players:
            df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values
