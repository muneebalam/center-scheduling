import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)



def add_child_2_staff_indicator(model: ConcreteModel) -> ConcreteModel:
    """
    Add a constraint to indicate when a child has two staff.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraint will be added.

    Returns:
        ConcreteModel: The model with the constraint added.
    """
    model.z_child_2_staff_hrs = Var(model.INDEX_DF["Time Block"].unique(), 
                                  model.INDEX_DF["Child"].unique(),
                                  within=Binary)
    
    model.child_2_staff_constraints = ConstraintList()
    for (time_block, child), df in model.INDEX_DF.groupby(["Time Block", "Child"]):
        n_staff = sum(model.X[time_block, child, staff]
                        for staff in df.Staff)
        # if n_staff == 2, then z_child_2_staff_hrs = 1
        # else, z_child_2_staff_hrs = 0
        model.child_2_staff_constraints.add(
            expr= n_staff <= model.z_child_2_staff_hrs[time_block, child] + 1
        )
    return model


def add_switch_indicator(model: ConcreteModel) -> ConcreteModel:
    """
    Add a constraint to indicate when a staff switches between children.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraint will be added.

    Returns:
        ConcreteModel: The model with the constraint added.
    """
    model.z_switch = Var(model.INDEX_DF["Time Block"].unique(), 
                                  model.INDEX_DF["Staff"].unique(),
                                  within=Binary)
    
    model.switch_constraints = ConstraintList()
    
    for (time_block, staff, child), df in model.INDEX_DF.groupby(["Time Block", "Staff", "Child"]):
        next_time_block = time_block + 1
        if next_time_block > max(model.INDEX_DF["Time Block"]):
            continue
        # if staff switches between children, then z_switch = 1
        # else, z_switch = 0
        mydiff = model.X[time_block, child, staff] - model.X[next_time_block, child, staff]
        model.switch_constraints.add(
            expr = mydiff <= model.z_switch[time_block, staff]
        )
        model.switch_constraints.add(
            expr = -1 * mydiff <= model.z_switch[time_block, staff]
        )
    return model


# Indicators ------------------------------------------------------------------

def add_child_no_staff_indicator(model: ConcreteModel) -> ConcreteModel:
    """
    Add a constraint to indicate when a child does not have staff.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraint will be added.

    Returns:
        ConcreteModel: The model with the constraint added.
    """
    model.z_child_no_staff = Var(model.INDEX_DF["Time Block"].unique(), 
                                  model.INDEX_DF["Child"].unique(),
                                  within=Binary)
    
    model.child_no_staff_constraints = ConstraintList()
    for (time_block, child), df in model.INDEX_DF.groupby(["Time Block", "Child"]):
        n_staff = sum(model.X[time_block, child, staff]
                        for staff in df.Staff)
        # if n_staff == 0, then z_child_no_staff = 1
        # else, z_child_no_staff = 0
        model.child_no_staff_constraints.add(
            expr= n_staff >= (1 - model.z_child_no_staff[time_block, child])
        )
    return model
