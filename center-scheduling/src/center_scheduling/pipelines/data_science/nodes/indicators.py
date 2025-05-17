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
    model.z_child_2_staff_hrs = Var(model.DAYS, 
                                     model.TIME_BLOCKS, 
                                     model.CHILDREN,
                                     within=Binary)
    
    model.child_2_staff_constraints = ConstraintList()
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            for child in model.CHILDREN:
                n_staff = sum(model.X[day, time_block, child, staff]
                              for staff in model.STAFF)
                # if n_staff == 2, then z_child_2_staff_hrs = 1
                # else, z_child_2_staff_hrs = 0
                model.child_2_staff_constraints.add(
                    expr= n_staff <= model.z_child_2_staff_hrs[day, time_block, child] + 1
                )
    return model

def add_staff_not_fully_used_indicator(model: ConcreteModel) -> ConcreteModel:
    """
    Add a constraint to indicate when a staff is not fully used.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraint will be added.

    Returns:
        ConcreteModel: The model with the constraint added.
    """
    return model
    model.z_staff_not_fully_used = Var(model.DAYS, 
                                        model.TIME_BLOCKS, 
                                        model.STAFF,
                                        within=Binary)
    
    model.staff_not_fully_used_constraints = ConstraintList()
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            for staff in model.STAFF:
                empty_time_blocks = sum(1 - model.X[day, time_block, child, staff]
                                        for child in model.CHILDREN)
                # if empty time blocks = 1, then z_staff_not_fully_used = 1
                # else, z_staff_not_fully_used = 0
                model.staff_not_fully_used_constraints.add(
                    expr= empty_time_blocks >= (1 - model.z_staff_not_fully_used[day, time_block, staff])
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
    model.z_switch = Var(model.DAYS, 
                         model.TIME_BLOCKS, 
                         model.STAFF,
                         within=Binary)
    
    model.switch_constraints = ConstraintList()
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            next_time_block = time_block + 1
            if next_time_block > max(model.TIME_BLOCKS):
                continue
            for child in model.CHILDREN:
                for staff in model.STAFF:
                    # if staff switches between children, then z_switch = 1
                    # else, z_switch = 0
                    mydiff = model.X[day, time_block, child, staff] - model.X[day, next_time_block, child, staff]
                    model.switch_constraints.add(
                        expr = mydiff <= model.z_switch[day, time_block, staff]
                    )
                    model.switch_constraints.add(
                        expr = -1 * mydiff <= model.z_switch[day, time_block, staff]
                    )
    return model