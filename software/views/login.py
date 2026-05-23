import streamlit as st
from db.postgres_manager import verify_login
import time

st.title("SMILE-IoT")
st.subheader("Access Authentication")



with st.form("login_form"):
    username = st.text_input("User")
    password = st.text_input("Password", type="password")
    submit = st.form_submit_button("Enter", type="primary", use_container_width=True)

    if submit:
        user_data = verify_login(username, password)
        if user_data:
            st.session_state.logged_in = True
            st.session_state.user_info = user_data
            st.session_state.last_active = time.time()
            st.rerun()
        else:
            st.error("Invalid Credentials! Try again")