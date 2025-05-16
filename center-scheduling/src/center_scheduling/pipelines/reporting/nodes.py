import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)

def combine_outputs(df1, df2, df3, df4, df5):
    """
    Combine the outputs of the 5 models into a single DataFrame.
    """
    # Concatenate the DataFrames
    return pd.concat([df1, df2, df3, df4, df5], ignore_index=True)