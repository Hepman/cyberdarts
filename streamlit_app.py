if submit_match:
                # Aktuelle Daten holen
                p1 = next(p for p in players if p['username'] == winner_name)
                p2 = next(p for p in players if p['username'] == loser_name)
                
                # Elo berechnen
                old_e1, old_e2 = p1['elo_score'], p2['elo_score']
                new_e1, new_e2 = calculate_elo(old_e1, old_e2, True)
                diff = new_e1 - old_e1
                
                # In DB speichern
                conn.table("profiles").update({"elo_score": new_e1, "games_played": p1['games_played']+1}).eq("id", p1['id']).execute()
                conn.table("profiles").update({"elo_score": new_e2, "games_played": p2['games_played']+1}).eq("id", p2['id']).execute()
                
                # Info im "Gedächtnis" speichern, damit sie nach rerun noch da ist
                st.session_state.last_match = f"✅ Match gewertet: {winner_name} (+{diff}) | {loser_name} (-{diff})"
                
                st.rerun()

    # Info-Box anzeigen, falls ein Match gerade gewertet wurde
    if 'last_match' in st.session_state:
        st.success(st.session_state.last_match)
        if st.button("OK, verstanden"):
            del st.session_state.last_match
            st.rerun()
