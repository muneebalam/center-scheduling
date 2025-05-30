import streamlit as st
import yaml
import os
from kedro_datasets.pandas import ExcelDataset
import pandas as pd
import sys
from kedro.framework.session import KedroSession

sys.path.append("center-scheduling")


st.title("Center Scheduling")

st.write("This is a web app to schedule staff for a center.")

st.write("Upload the center data to get started.")

uploaded_file = st.file_uploader("Upload the center data", type="xlsx")

BASE_FOLDER = "center-scheduling"

with open(os.path.join(BASE_FOLDER, "conf/base/catalog.yml"), "r") as f:
    catalog = yaml.safe_load(f)

example_data = {}
new_data = {}

# Read the example files
for key in catalog:
    fpath = catalog[key]["filepath"]
    if "01_raw" in fpath:
        sheet_name = catalog[key]["load_args"]["sheet_name"]
        example_data[sheet_name] = pd.read_excel(os.path.join(BASE_FOLDER, fpath), 
                                                sheet_name=sheet_name)
    
if uploaded_file is not None:
    # First, read required tabs
    multiframe = {}
    keys = ["center_hours", "staff_child", "absences", "roles"]

    for key in keys:
        sheet_name = catalog[key]["load_args"]["sheet_name"]
        multiframe[sheet_name] = pd.read_excel(uploaded_file, sheet_name=sheet_name)

    # Then, save the data to the local (not base) catalog
    local_catalog = os.path.join(BASE_FOLDER, "conf/local/catalog.yml")
    fpath = os.path.join(BASE_FOLDER, local_catalog["center_hours"]["filepath"])
    dataset = ExcelDataset(filepath=fpath, load_args = {"sheet_name": None})
    dataset.save(multiframe)
    st.write("Upload successful")

    for key in local_catalog:
        fpath = local_catalog[key]["filepath"]
        if "01_raw" in fpath:
            sheet_name = local_catalog[key]["load_args"]["sheet_name"]
            new_data[sheet_name] = pd.read_excel(os.path.join(BASE_FOLDER, fpath), 
                                                sheet_name=sheet_name)

for k, v in example_data.items():
    with st.expander(f"Example {k}"):
        st.dataframe(v, hide_index=True)
    if k in new_data:
        with st.expander(f"Uploaded {k}"):
            st.dataframe(new_data[k], hide_index=True)

env_selection = st.selectbox("Select environment", ["example", "uploaded"])
env_to_run = {"example": "base", "uploaded": "local"}[env_selection]
if st.button("Run pipeline"):
    with st.spinner("Running pipeline..."):
        with KedroSession.create(BASE_FOLDER, env=env_to_run) as session:
            session.run()
            