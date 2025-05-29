# Introduction

# Installation

`conda env create --name sch python=3.12`

`pip install -r center-scheduling/requirements.txt`

# Development

`conda activate sch`

`kedro run`

`streamlit run app.py`

If you install another package:

`conda env export > environment.yaml`
`pip freeze > requirements.txt`

(Yes, the environment is inconsistent for now.)