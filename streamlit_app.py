import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Cyber-Design CSS
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; border-radius: 5px; border: none; }
    .stTextInput>div>div>input { background-color: #1a1c23; color: #00d4ff; border: 1px solid #00d4ff; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    try:
        return st.connection("supabase", type=SupabaseConnection, 
                             url=st.secrets["connections"]["supabase"]["url"], 
                             key=st.secrets["connections"]["supabase"]["key"])
    except Exception as e:
        st.error(f"Verbindung fehlgeschlagen: {e}")
        return None

conn = init_connection()

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        new_a = round(rating_a + k * (1 - prob_a))
        new_b = round(rating_b + k * (0 - (1 - prob_a)))
    else:
        new_a = round(rating_a + k * (0 - prob_a))
        new_b = round(rating_b + k * (1 - (1 - prob_a)))
    return new_a, new_b

# --- DATEN LADEN ---
players = []
recent_matches = []
if conn:
    p_res = conn.table("profiles").select("*").execute()
    players = p_res.data or []
    m_res = conn.table("matches").select("*").order("created_at", desc=True).execute()
    recent_matches = m_res.data or []

st.
