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

if uploaded_file is not None:
    # First, read required tabs
    with open(os.path.join(BASE_FOLDER, "conf/base/catalog.yml"), "r") as f:
        catalog = yaml.safe_load(f)

    keys = ["center_hours", "staff_child", "absences", "roles"]
    multiframe = {}

    for key in keys:
        sheet_name = catalog[key]["load_args"]["sheet_name"]
        multiframe[sheet_name] = pd.read_excel(uploaded_file, sheet_name=sheet_name)

    # Then, save the data to the local (not base) catalog
    local_catalog = os.path.join(BASE_FOLDER, "conf/local/catalog.yml")
    fpath = os.path.join(BASE_FOLDER, local_catalog["center_hours"]["load_args"]["filepath"])
    dataset = ExcelDataset(filepath=fpath, load_args = {"sheet_name": None})
    dataset.save(multiframe)
    st.write("Upload successful")