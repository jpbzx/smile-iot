import streamlit as st
from db.postgres_manager import create_password_reset_request, reset_password_with_token
from utils.emailer import send_password_reset_email

st.title("SMILE-IoT — Password Recovery")

params = st.experimental_get_query_params()
token = params.get("token", [None])[0]

if token:
    st.subheader("Set a new password")
    with st.form("reset_form"):
        pw = st.text_input("New password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        submit = st.form_submit_button("Reset password")

        if submit:
            if not pw or not pw2:
                st.error("Please fill both password fields")
            elif pw != pw2:
                st.error("Passwords do not match")
            else:
                ok, msg = reset_password_with_token(token, pw)
                if ok:
                    st.success("Password updated successfully. You can now login.")
                    # Clear token from URL
                    st.experimental_set_query_params()
                else:
                    st.error(f"Failed to reset password: {msg}")

else:
    st.subheader("Request password reset")
    st.write("Enter the email associated with your account. We'll send a reset link.")
    with st.form("request_form"):
        email = st.text_input("Email")
        submit = st.form_submit_button("Send reset email")

        if submit:
            if not email:
                st.error("Please provide an email address")
            else:
                ok, token_or_err = create_password_reset_request(email)
                if not ok:
                    st.error(token_or_err)
                else:
                    token = token_or_err
                    ok_send, err = send_password_reset_email(email, token)
                    if ok_send:
                        st.success("Reset email sent. Check your inbox and spam folder.")
                    else:
                        st.error(f"Error sending email: {err}")
