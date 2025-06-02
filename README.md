# Introduction

# Installation

`conda env create --name sch python=3.10`

`uv sync`

You may also need

`conda install glpk`

`conda install conda-forge::coin-or-cbc`

If on Mac, you can also install these using brew

`brew install glpk cbc`

# Development

`conda activate sch`

`uv run kedro run --env=base`

`uv run streamlit run app.py`

If you install another package:

`uv add mypackage`

`uv lock`

`uv pip compile pyproject.toml -o requirements.txt`
