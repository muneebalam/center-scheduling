import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)

from .setup import _24h_time_to_index

def _clean_start_end(model: ConcreteModel, row: pd.Series) -> tuple[int, int]:
    start = row["Start"]
    end = row["End"]
    if start is None or pd.isna(start):
        start = min(model.TIME_BLOCKS)
    if end is None or pd.isna(end):
        end = max(model.TIME_BLOCKS)
    return int(start), int(end)

def add_pto_constraints(model: ConcreteModel) -> ConcreteModel:
    model.pto_constraints = ConstraintList()
    pto = model.ABSENCES.pipe(lambda x: x[x.Type == "PTO"])[["Name", "Start", "End"]]
    for _, row in pto.iterrows():
        start, end = _clean_start_end(model, row)
        for i in range(start, end):
            model.pto_constraints.add(
                expr=sum(model.X[day, i, child, row["Name"]]
                         for day in model.DAYS
                         for child in model.CHILDREN) == 0
            )
    return model

def add_parent_training_constraints(model: ConcreteModel) -> ConcreteModel:
    model.parent_training_constraints = ConstraintList()
    parent_training = model.ABSENCES.pipe(lambda x: x[x.Type == "Parent Training"])[["Name", "Start", "End"]]
    for _, row in parent_training.iterrows():
        start, end = _clean_start_end(model, row)
        for i in range(start, end):
            model.parent_training_constraints.add(
                expr=sum(model.X[day, i, child, row["Name"]]
                         for day in model.DAYS
                         for child in model.CHILDREN) == 0
            )
    return model

def add_team_meeting_constraints(model: ConcreteModel) -> ConcreteModel:
    model.team_meeting_constraints = ConstraintList()
    team_meeting = model.ABSENCES.pipe(lambda x: x[x.Type == "Team Meeting"])[["Name", "Start", "End"]]
    for _, row in team_meeting.iterrows():
        start, end = _clean_start_end(model, row)
        for i in range(start, end):
            model.team_meeting_constraints.add(
                expr=sum(model.X[day, i, child, staff]
                         for day in model.DAYS
                         for child in model.CHILDREN
                         for staff in model.STAFF) == 0
            )
    return model

def add_nap_time_constraints(model: ConcreteModel) -> ConcreteModel:
    model.nap_time_constraints = ConstraintList()
    nap_rows = model.ABSENCES.pipe(lambda x: x[x.Type == "Nap"])[["Name", "Start", "End"]]
    for _, row in nap_rows.iterrows():
        start, end = _clean_start_end(model, row)
        for i in range(start, end):
            model.nap_time_constraints.add(
                expr=sum(model.X[day, i, row["Name"], staff]
                         for day in model.DAYS
                         for staff in model.STAFF) == 0
            )
    return model

def add_speech_therapy_constraints(model: ConcreteModel) -> ConcreteModel:
    model.speech_constraints = ConstraintList()
    speech_therapy = model.ABSENCES.pipe(lambda x: x[x.Type == "Speech"])[["Name", "Start", "End"]]
    for _, row in speech_therapy.iterrows():
        start, end = _clean_start_end(model, row)
        for i in range(start, end):
            model.speech_constraints.add(
                expr=sum(model.X[day, i, row["Name"], staff]
                         for day in model.DAYS
                         for staff in model.STAFF) == 0
            )
    return model

def center_hours_constraints(model: ConcreteModel) -> ConcreteModel:
                             for staff in model.STAFF) == 0
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
    lunch_start = _24h_time_to_index(12)
    lunch_end = _24h_time_to_index(14)
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
