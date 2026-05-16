import streamlit as st
from db.postgres_manager import verify_login, create_password_reset_request, reset_password_with_token
from utils.emailer import send_password_reset_email
import time

st.title("SMILE-IoT")
st.subheader("Access Authentication")

# Initialize session state keys used for password reset flow
st.session_state.setdefault("last_reset_request_at", 0)
st.session_state.setdefault("reset_request_cooldown", 60)  # seconds

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

# -- Password reset request (Forgot password) --
st.markdown("---")
st.write("If you forgot your password, you can request a reset link via email.")
with st.form("forgot_form"):
    email = st.text_input("Email for password reset")
    send_btn = st.form_submit_button("Send reset email")

    if send_btn:
        now = time.time()
        cooldown = st.session_state.reset_request_cooldown
        if now - st.session_state.last_reset_request_at < cooldown:
            st.warning("Please wait before requesting another reset email.")
        else:
            # create token and send email; do not leak whether email exists
            ok, token_or_err = create_password_reset_request(email)
            # Always show a neutral message to avoid user enumeration
            if ok:
                token = token_or_err
                ok_send, err = send_password_reset_email(email, token)
                if ok_send:
                    st.success("If the email exists in our system, a reset link has been sent.")
                else:
                    st.error("Failed to send reset email. Contact support.")
            else:
                # Logically could be 'Email not found' — still show neutral message
                st.success("If the email exists in our system, a reset link has been sent.")

            st.session_state.last_reset_request_at = now

# -- Reset with token (user pastes token from email) --
st.markdown("---")
st.write("Have a reset token? Paste it below along with a new password.")
with st.form("use_token_form"):
    token = st.text_input("Reset token (from email)")
    new_pw = st.text_input("New password", type="password")
    new_pw2 = st.text_input("Confirm new password", type="password")
    use_token_btn = st.form_submit_button("Reset password")

    if use_token_btn:
        if not token or not new_pw or not new_pw2:
            st.error("Please fill all fields")
        elif new_pw != new_pw2:
            st.error("Passwords do not match")
        else:
            ok, msg = reset_password_with_token(token, new_pw)
            if ok:
                st.success("Password updated. Please login with your new password.")
            else:
                st.error(f"Failed to reset password: {msg}")