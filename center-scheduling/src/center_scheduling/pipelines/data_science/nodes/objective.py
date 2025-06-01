import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)



# Objective and solve -----------------------------------------------------------------

def add_objective(model: ConcreteModel, reward_for_child_staff_role: dict) -> ConcreteModel:
    """
    Add an objective function to the model.

    Args:
        model (ConcreteModel): The Pyomo model to which the objective will be added.

    Returns:
        ConcreteModel: The model with the objective function added.
    """
    # Define the objective function
    # Maximize child hours - preference to techs though
    child_hr_objs = {}
    for role, reward in reward_for_child_staff_role.items():
        relevant_staff = model.ROLES.pipe(lambda x: x[x.Role.str.lower() == role.lower()])["Name"]
        relevant_staff = [x for x in relevant_staff if x in model.INDEX_DF["Staff"].unique()]
        relevant_vars = model.INDEX_DF[model.INDEX_DF["Staff"].isin(relevant_staff)]
        if len(relevant_vars) > 0:
            child_hr_objs[role] = sum([model.X[time_block, child, staff]
                                          for (time_block, staff, child), df 
                                          in relevant_vars.groupby(["Time Block", "Staff", "Child"])]) * reward

    # Penalize when children have two staff
    child_2_staff_hrs = sum([model.z_child_2_staff_hrs[time_block, child]
                                          for (time_block, child), _ in model.INDEX_DF.groupby(["Time Block", "Child"])])
    # Penalize switches
    child_switch_hrs = sum([model.z_switch[time_block, staff]
                                          for (time_block, staff), _ in model.INDEX_DF.groupby(["Time Block", "Staff"])])

    
    model.objective = Objective(expr=sum(child_hr_objs.values())
                                - child_2_staff_hrs
                                - child_switch_hrs * 0.1, 
                                sense=maximize)
    return model