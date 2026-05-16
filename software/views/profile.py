import streamlit as st
from db.postgres_manager import update_password
import time

# Authentication guard
if not st.session_state.get("logged_in"):
    st.error("Authentication required. Please login.")
    st.stop()
else:
    st.session_state.last_active = time.time()

st.title("👤 My Projile")
st.write(f"**Username:** {st.session_state.user_info['username']}")
st.write(f"**Role:** {st.session_state.user_info['role'].capitalize()}")

st.markdown("---")
st.subheader("Change password")

with st.form("new_user_form", clear_on_submit=True):
    nova_pass = st.text_input("New Password", type="password")
    confirmar_pass = st.text_input("Confirm New Password", type="password")
    
    submit_pass = st.form_submit_button("Update Password")
    
    if submit_pass:
        if len(nova_pass) < 5:
            st.error("A password tem de ter pelo menos 5 caracteres.")
        elif nova_pass != confirmar_pass:
            st.error("Passwords don't match")
        else:
            sucesso = update_password(st.session_state.user_info['id'], nova_pass)
            if sucesso:
                st.success("Password updated successfuly")
            else:
                st.error("ERROR[?]")