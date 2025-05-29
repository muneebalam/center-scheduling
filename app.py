import streamlit as st

st.title("Center Scheduling")

st.write("This is a web app to schedule staff for a center.")

st.write("Upload the center data to get started.")

st.file_uploader("Upload the center data", type="xlsx")
