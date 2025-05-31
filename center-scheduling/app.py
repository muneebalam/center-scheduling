import streamlit as st
import yaml
import os
from kedro_datasets.pandas import ExcelDataset
import pandas as pd
import sys
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
from pathlib import Path

# Get the original directory and cache

BASE_FOLDER = "center-scheduling"
KEYS = ["center_hours", "staff_child", "absences", "roles"]
@st.cache_data
def get_original_dir():
    return os.getcwd()
@st.cache_data
def get_original_catalog():
    with open(os.path.join(BASE_FOLDER, "conf/base/catalog.yml"), "r") as f:
        return yaml.safe_load(f)
@st.cache_data
def get_example_data(catalog):
    example_data = {}
    for key in catalog:
        fpath = catalog[key]["filepath"]
        if "01_raw" in fpath:
            sheet_name = catalog[key]["load_args"]["sheet_name"]
            example_data[sheet_name] = pd.read_excel(os.path.join(BASE_FOLDER, fpath), 
                                                    sheet_name=sheet_name)
    return example_data

ORIGINAL_WD = get_original_dir()
os.chdir(ORIGINAL_WD)
ORIGINAL_CATALOG = get_original_catalog()

sys.path.append("center-scheduling")
st.title("Center Scheduling")
st.write("This is a web app to schedule staff for a center.")
st.write("Upload the center data to get started.")
uploaded_file = st.file_uploader("Upload the center data", type="xlsx")

example_data = get_example_data(ORIGINAL_CATALOG)
new_data = {}

if uploaded_file is not None:
    # First, read required tabs
    multiframe = {}

    for key in KEYS:
        sheet_name = ORIGINAL_CATALOG[key]["load_args"]["sheet_name"]
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

# If you are creating a session outside of a Kedro project (i.e. not using
# `kedro run` or `kedro jupyter`), you need to run `bootstrap_project` to
# let Kedro find your configuration.
#bootstrap_project(Path(BASE_FOLDER))
env_selection = st.selectbox("Select environment", ["example", "uploaded"])
env_to_run = {"example": "base", "uploaded": "local"}[env_selection]
if st.button("Run pipeline"):
    with st.spinner("Running pipeline..."):
        os.chdir(ORIGINAL_WD)
        os.system(f"cd center-scheduling && uv run kedro run --env={env_to_run}")
        #with KedroSession.create(BASE_FOLDER, env=env_to_run) as session:
        #    session.run()
            