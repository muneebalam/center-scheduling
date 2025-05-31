import streamlit as st
import yaml
import os
from kedro_datasets.pandas import ExcelDataset
import pandas as pd
import sys
import subprocess

# Get the original directory and cache
BASE_FOLDER = "center_scheduling"
KEYS = ["center_hours", "staff_child", "absences", "roles"]
@st.cache_data
def get_original_dir():
    return os.getcwd()
ORIGINAL_WD = get_original_dir()
def get_catalog(env):
    os.chdir(ORIGINAL_WD)
    cat_path = os.path.join(ORIGINAL_WD, BASE_FOLDER, "conf", env, "catalog.yml")
    assert os.path.exists(cat_path), f"Catalog not found at {cat_path}"
    with open(cat_path, "r") as f:
        return yaml.safe_load(f)
@st.cache_data
def get_original_catalog():
    return get_catalog("base")
@st.cache_data
def get_local_catalog():
    return get_catalog("local")
@st.cache_data
def get_example_data(catalog):
    example_data = {}
    for key in catalog:
        fpath = catalog[key]["filepath"]
        if "01_raw" in fpath:
            sheet_name = catalog[key]["load_args"]["sheet_name"]
            example_data[sheet_name] = pd.read_excel(fpath, 
                                                    sheet_name=sheet_name)
    return example_data

os.chdir(ORIGINAL_WD)
ORIGINAL_CATALOG = get_original_catalog()
LOCAL_CATALOG = get_local_catalog()
example_data = get_example_data(ORIGINAL_CATALOG)

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
        fpath = LOCAL_CATALOG["center_hours"]["filepath"]
        dataset = ExcelDataset(filepath=fpath, load_args = {"sheet_name": None})
        dataset.save(multiframe)
        st.write("Upload successful")

        for key in LOCAL_CATALOG:
            fpath = LOCAL_CATALOG[key]["filepath"]
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
    if st.button("Run pipeline"):
        with st.spinner("Running pipeline..."):
            os.chdir(ORIGINAL_WD)
            command = ["uv", "run", "kedro", "run", f"--env={env_to_run}"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)


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

with st.container(border=True):
    st.markdown("# Results")

    res_tabs = st.tabs(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Log"])
    try:
        results = [pd.read_csv(f"data/08_reporting/d{i}_solution.csv") for i in range(1, 6)]
        res_styled = [result.drop("Day", axis=1)
                        .set_index("Time Block")
                        .style.applymap(_apply_bg_color) for result in results]
        for i, result in enumerate(res_styled):
            with res_tabs[i]:
                st.dataframe(result)
        with res_tabs[-1]:
            st.markdown("## Run log")
            if process is not None:
                while process.poll() is None:
                    line = process.stdout.readline()
                    if not line:
                        continue
                    st.write(line.strip())
    except FileNotFoundError:
        pass
                