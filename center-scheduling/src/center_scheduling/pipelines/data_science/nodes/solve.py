import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)

from .setup import _24h_time_to_index, _index_to_24h_time


def solve(model: ConcreteModel) -> ConcreteModel:
    """
    Solve the optimization model with optimized settings.

    Args:
        model (ConcreteModel): The Pyomo model to be solved.

    Returns:
        ConcreteModel: The solved model.
    """
    # Set solver options
    solver = SolverFactory('cbc') #glpk
    solver.options['threads'] = 4    # Use multiple threads if available
    solver.options['ratio'] = 0.01   # Set gap tolerance to 1%
    solver.options['heur'] = 'on'    # Enable heuristics
    
    # Solve with optimized settings
    results = solver.solve(model, tee=True)
    
    return model

def print_solution(model: ConcreteModel) -> pd.DataFrame:
    """
    Print the solution of the model.

    Args:
        model (ConcreteModel): The solved Pyomo model.
    """
    # Iterate through the decision variables and print their values
    results_df = pd.DataFrame({}, columns=["Day", "Time Block", "Child", "Staff"])
    for (time_block, child, staff), _ in model.INDEX_DF.groupby(["Time Block", "Child", "Staff"]):
        if model.X[time_block, child, staff].value > 0:
            results_df = pd.concat([results_df, pd.DataFrame({
                "Day": [model.DAY],
                "Time Block": [time_block],
                "Child": [child],
                "Staff": [staff]
            })], ignore_index=True)
    results_df_wide = (
        results_df
        .pivot(index=["Day", "Time Block"], columns = "Staff", values = "Child")
        .reset_index()
        .sort_values("Time Block")
        .assign(**{"Time Block": lambda x: x["Time Block"].apply(_index_to_24h_time)})
    )
    return results_df_wide