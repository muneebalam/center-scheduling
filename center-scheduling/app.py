import streamlit as st
import yaml
import os
from kedro_datasets.pandas import ExcelDataset
import pandas as pd
import sys
import subprocess

# Get the original directory and cache
BASE_FOLDER = "center-scheduling"
KEYS = ["center_hours", "staff_child", "absences", "roles"]
@st.cache_data
def _get_original_dir():
    cwd = os.getcwd()
    return cwd
ORIGINAL_WD = _get_original_dir()
NEEDED_WD = os.path.join(ORIGINAL_WD, BASE_FOLDER) if BASE_FOLDER in os.listdir(ORIGINAL_WD) else ORIGINAL_WD
def _get_catalog(env):
    cat_path = os.path.join(NEEDED_WD,"conf", env, "catalog.yml")
    with open(cat_path, "r") as f:
        return yaml.safe_load(f)
@st.cache_data
def _get_original_catalog():
    return _get_catalog("base")
@st.cache_data
def _get_local_catalog():
    return _get_catalog("local")
@st.cache_data
def _get_example_data(catalog):
    example_data = {}
    for key in catalog:
        fpath = os.path.join(NEEDED_WD, catalog[key]["filepath"])
        if "01_raw" in fpath:
            sheet_name = catalog[key]["load_args"]["sheet_name"]
            example_data[sheet_name] = pd.read_excel(fpath, 
                                                    sheet_name=sheet_name)
    return example_data

ORIGINAL_CATALOG = _get_original_catalog()
LOCAL_CATALOG = _get_local_catalog()
example_data = _get_example_data(ORIGINAL_CATALOG)

sys.path.append("center-scheduling")

st.title("Center Scheduling")
st.write("This is a web app to schedule staff for a center.")

process = None
with st.container(border=True):
    st.markdown("# Setup")
    st.write("Upload the center data to get started.")
    uploaded_file = st.file_uploader("Upload the center data", type="xlsx")
    new_data = {}

    # If the user uploads a file, read it and save it to the local catalog
    if uploaded_file is not None:
        # First, read required tabs
        multiframe = {}

        for key in KEYS:
            sheet_name = ORIGINAL_CATALOG[key]["load_args"]["sheet_name"]
            multiframe[sheet_name] = pd.read_excel(uploaded_file, sheet_name=sheet_name)

        # Then, save the data to the local (not base) catalog
        fpath = os.path.join(NEEDED_WD, LOCAL_CATALOG["center_hours"]["filepath"])
        dataset = ExcelDataset(filepath=fpath, load_args = {"sheet_name": None})
        dataset.save(multiframe)
        st.write("Upload successful")

        for key in LOCAL_CATALOG:
            fpath = os.path.join(NEEDED_WD, LOCAL_CATALOG[key]["filepath"])
            if "01_raw" in fpath:
                sheet_name = LOCAL_CATALOG[key]["load_args"]["sheet_name"]
                new_data[sheet_name] = pd.read_excel(fpath, 
                                                    sheet_name=sheet_name)

    for k, v in example_data.items():
        with st.expander(f"Example {k}"):
            st.dataframe(v, hide_index=True)
        if k in new_data:
            with st.expander(f"Uploaded {k}"):
                st.dataframe(new_data[k], hide_index=True)

    env_selection = st.selectbox("Select environment", ["example", "uploaded"])
    env_to_run = {"example": "base", "uploaded": "local"}[env_selection]


def _apply_bg_color(elem):
    if elem is None or elem == "" or pd.isnull(elem):
        return "background-color: white"
    
    assert isinstance(elem, str), f"Expected string, got {elem}"
    font_color = "white" if "dark" in elem else "black"

    color_replacements = {"darkdarkblue": "midnightblue", "darkpurple": "indigo", 
                        "lightpurple": "mediumpurple", "darkpink": "mediumvioletred", 
                        "paleyellow": "lemonchiffon", "lightorange": "bisque", }
    if elem in color_replacements:
        elem = color_replacements[elem]
    return_str = f"background-color: {elem}; color: {font_color}"
    return return_str

if st.button("Run pipeline"):
    os.chdir(NEEDED_WD)
    command = ["uv", "run", "kedro", "run", f"--env={env_to_run}", "--runner", "ParallelRunner"]
    with open("test.log", "wb") as f:
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        for c in iter(lambda: process.stdout.read(1), b""):
            f.write(c)
    os.chdir(ORIGINAL_WD)

with st.expander("Live log"):
    st.write(ORIGINAL_WD)
    st.write(NEEDED_WD)
    if os.path.exists("test.log"):
        with open("test.log", "r") as f:
            for line in f:
                st.write(line)

with st.container(border=True):
    st.markdown("# Results")
    if st.button("Refresh results"):
        res_tabs = st.tabs(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        all_results = []
        for i in range(len(res_tabs)):
            with res_tabs[i]:
                try:
                    result = pd.read_csv(os.path.join(NEEDED_WD, "data", "08_reporting", f"d{i+1}_solution.csv"))
                    all_results.append(result)
                    styled = (
                        result
                        .drop("Day", axis=1)
                        .set_index("Time Block")
                    .style.applymap(_apply_bg_color)
                )
                    st.dataframe(styled)
                except FileNotFoundError:
                    st.write("No results yet")
        
        try:
            results = pd.concat(all_results)
            csv = results.to_csv(index=False).encode('utf-8')

            if len(all_results) == 5:
                st.download_button(
                    "Download",
                    csv,
                    "solution.csv",
                    "text/csv",
                    key='download-csv'
                )
        except FileNotFoundError:
            st.write("No compiled results yet")
                