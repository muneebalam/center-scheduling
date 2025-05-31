# Introduction

# Installation

`conda env create --name sch python=3.8`

`uv sync`

# Development

`conda activate sch`

`uv run kedro run --env=base`

`streamlit run app.py`

If you install another package:

`uv add mypackage`

`uv lock`
