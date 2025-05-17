import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)



def add_pto_constraints(model: ConcreteModel) -> ConcreteModel:
    model.pto_constraints = ConstraintList()
    pto = model.ABSENCES.pipe(lambda x: x[x.Type == "PTO"])[["Name", "Start", "End"]]
    for _, row in pto.iterrows():
        start = row["Start"]
        end = row["End"]
        if start is None:
            start = min(model.TIME_BLOCKS)
        if end is None:
            end = max(model.TIME_BLOCKS)
        for i in range(start, end):
            model.pto_constraints.add(
                expr=sum(model.X[day, i, child, row["Name"]]
                         for day in model.DAYS
                         for child in model.CHILDREN) == 0
            )
    return model

def center_hours_constraints(model: ConcreteModel) -> ConcreteModel:
    """
    Add constraints to ensure that the center is open during specified hours.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraints will be added.

    Returns:
        ConcreteModel: The model with the constraints added.
    """
    model.center_hours_constraints = ConstraintList()
    for _, row in model.CENTER_HOURS.iterrows():
        day = row["Day"]
        start_time = _24h_time_to_index(row["Open"])
        end_time = _24h_time_to_index(row["Close"])
        for time_block in model.TIME_BLOCKS:
            if time_block < start_time or time_block >= end_time:
                # Add constraints to the model
                model.center_hours_constraints.add(
                    expr=sum(model.X[day, time_block, child, staff]
                             for child in model.CHILDREN
                             for staff in model.STAFF) == 0
                )
    return model

def add_staff_child_constraints(model: ConcreteModel) -> ConcreteModel:
    model.staff_child_constraints = ConstraintList()
    for child, staff_df in model.STAFF_CHILD.groupby("Child"):
        acceptable_staff = staff_df.Staff
        unacceptable_staff = model.STAFF[~pd.Series(model.STAFF).isin(acceptable_staff)]
        for staff in unacceptable_staff:
            for day in model.DAYS:
                for time_block in model.TIME_BLOCKS:
                    # Add constraints to the model
                    model.staff_child_constraints.add(
                        expr=model.X[day, time_block, child, staff] == 0
                    )
    return model

def add_one_place_per_time_constraint(model: ConcreteModel) -> ConcreteModel:
    """
    Add a constraint to ensure that each staff is in one place at a time.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraint will be added.

    Returns:
        ConcreteModel: The model with the constraint added.
    """
    model.one_place_per_time = ConstraintList()
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            for staff in model.STAFF:
                # Add constraints to the model
                model.one_place_per_time.add(
                    expr=sum(model.X[day, time_block, child, staff]
                             for child in model.CHILDREN) <= 1
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
    model.z_child_no_staff = Var(model.DAYS, 
                                  model.TIME_BLOCKS, 
                                  model.CHILDREN,
                                  within=Binary)
    
    model.child_no_staff_constraints = ConstraintList()
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            for child in model.CHILDREN:
                n_staff = sum(model.X[day, time_block, child, staff]
                              for staff in model.STAFF)
                # if n_staff == 0, then z_child_no_staff = 1
                # else, z_child_no_staff = 0
                model.child_no_staff_constraints.add(
                    expr= n_staff >= (1 - model.z_child_no_staff[day, time_block, child])
                )
    return model

def add_junior_staff_constraints(model: ConcreteModel) -> ConcreteModel:
    """
    Add constraints to ensure that junior staff are not assigned to children.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraints will be added.

    Returns:
        ConcreteModel: The model with the constraints added.
    """
    model.junior_staff_constraints = ConstraintList()
    for day in model.DAYS:
        for time_block in model.TIME_BLOCKS:
            for child in model.CHILDREN:
                model.junior_staff_constraints.add(
                    expr=sum([
                        model.X[day, time_block, child, staff] 
                        for staff in model.JSTAFF
                    ]) <= 1
                )
    return model

def add_lunch_constraints(model: ConcreteModel) -> ConcreteModel:
    """
    Add constraints to ensure that lunch is scheduled for each staff member between 12 and 2.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraints will be added.

    Returns:
        ConcreteModel: The model with the constraints added.
    """
    # Define the lunch time range
    lunch_start = _24h_time_to_index("12:00:00")
    lunch_end = _24h_time_to_index("14:00:00")
    span = lunch_end - lunch_start

    model.lunch_constraints = ConstraintList()
    for day in model.DAYS:
        for staff in model.STAFF:
            time_range_req = [x for x in list(range(lunch_start, lunch_end))
                              if x in model.TIME_BLOCKS]
            if len(time_range_req) == 0:
                continue
            model.lunch_constraints.add(
                expr=sum(model.X[day, time_block, child, staff]
                         for time_block in time_range_req
                         for child in model.CHILDREN) <= span - 1
            )
    return model
