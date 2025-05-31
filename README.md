# Introduction

# Installation

`conda env create --name sch python=3.8`

`uv sync`

You may also need

`conda install glpk`

# Development

`conda activate sch`

`uv run kedro run --env=base`

`uv run streamlit run app.py`

If you install another package:

`uv add mypackage`

`uv lock`
