import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)



def solve(model: ConcreteModel) -> ConcreteModel:
    """
    Solve the optimization model.

    Args:
        model (ConcreteModel): The Pyomo model to be solved.

    Returns:
        ConcreteModel: The solved model.
    """
    # Create a solver
    solver = SolverFactory('glpk')

    # Solve the model
    results = solver.solve(model, tee=True)

    # Check if the solver found a solution
    if results.solver.termination_condition == 'optimal':
        logger.info("Optimal solution found.")
    else:
        logger.info("Solver did not find an optimal solution.")

    return model

def print_solution(model: ConcreteModel) -> pd.DataFrame:
    """
    Print the solution of the model.

    Args:
        model (ConcreteModel): The solved Pyomo model.
    """
    # Iterate through the decision variables and print their values
    results_df = pd.DataFrame({}, columns=["Day", "Time Block", "Child", "Staff"])
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            for child in model.CHILDREN:
                for staff in model.STAFF:
                    if model.X[day, time_block, child, staff].value > 0:
                        results_df = pd.concat([results_df, pd.DataFrame({
                            "Day": [day],
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