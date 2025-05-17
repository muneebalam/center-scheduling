import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)

from .setup import _24h_time_to_index, _index_to_24h_time


def _clean_start_end(model: ConcreteModel, row: pd.Series) -> tuple[int, int]:
    start = row["Start"]
    end = row["End"]
    # Can be floats (e.g. 12.5 for 12:30)
    # or times like 12:30
    try:
        start = float(start) * 2
        end = float(end) * 2
        start, end= int(start), int(end)
    except ValueError:
        if start is None or pd.isna(start):
            start = min(model.TIME_BLOCKS)
        if end is None or pd.isna(end):
            end = max(model.TIME_BLOCKS)

    # Also make sure these do not exceed time blocks
    start = max(start, min(model.TIME_BLOCKS))
    end = min(end, max(model.TIME_BLOCKS))
    return int(start), int(end)

def add_pto_constraints(model: ConcreteModel) -> ConcreteModel:
    model.pto_constraints = ConstraintList()
    pto = model.ABSENCES.pipe(lambda x: x[x.Type == "PTO"])[["Name", "Day", "Start", "End"]]
    for _, row in pto.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        model.pto_constraints.add(
            expr=sum(model.X[i, child, row["Name"]]
                     for child in model.CHILDREN
                     for i in range(start, end)) == 0
        )
    return model

def add_parent_training_constraints(model: ConcreteModel) -> ConcreteModel:
    model.parent_training_constraints = ConstraintList()
    parent_training = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Parent Training"])[["Name", "Day", "Start", "End"]]
    for _, row in parent_training.iterrows():
        start, end = _clean_start_end(model, row)
        model.parent_training_constraints.add(
            expr=sum(model.X[i, child, row["Name"]]
                     for child in model.CHILDREN
                     for i in range(start, end)) == 0
        )
    return model

def add_team_meeting_constraints(model: ConcreteModel) -> ConcreteModel:
    model.team_meeting_constraints = ConstraintList()
    team_meeting = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Team Meeting"])[["Name", "Day", "Start", "End"]]
    for _, row in team_meeting.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        model.team_meeting_constraints.add(
            expr=sum(model.X[i, child, staff]
                     for child in model.CHILDREN
                     for staff in model.STAFF
                     for i in range(start, end)) == 0
        )
    return model

def add_nap_time_constraints(model: ConcreteModel) -> ConcreteModel:
    model.nap_time_constraints = ConstraintList()
    nap_rows = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Nap"])[["Name", "Day", "Start", "End"]]
    for _, row in nap_rows.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        model.nap_time_constraints.add(
            expr=sum(model.X[i, row["Name"], staff]
                     for staff in model.STAFF
                     for i in range(start, end)) == 0
        )
    return model

def add_speech_therapy_constraints(model: ConcreteModel) -> ConcreteModel:
    model.speech_constraints = ConstraintList()
    speech_therapy = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Speech"])[["Name", "Day", "Start", "End"]]
    for _, row in speech_therapy.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        model.speech_constraints.add(
            expr=sum(model.X[i, row["Name"], staff]
                     for staff in model.STAFF
                     for i in range(start, end)) == 0
        )
    return model

def add_arrival_departure_constraints(model: ConcreteModel) -> ConcreteModel:
    """
    Take kids who arrive late and leave early into account
    """
    arr_dep = (
        model.ABSENCES
        .pipe(lambda x: x[x.Type.str.lower().isin(["late arrival", "leaves early"])])
        [["Name", "Start", "End"]]
    )
    model.arrival_departure_constraints = ConstraintList()
    for _, row in arr_dep.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        model.arrival_departure_constraints.add(
            expr=sum(model.X[i, row["Name"], staff]
                     for staff in model.STAFF
                     for i in range(start, end)) == 0
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
            for time_block in model.TIME_BLOCKS:
                # Add constraints to the model
                model.staff_child_constraints.add(
                    expr=model.X[time_block, child, staff] == 0
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
    for time_block in model.TIME_BLOCKS:
        for staff in model.STAFF:
            # Add constraints to the model
            model.one_place_per_time.add(
                expr=sum(model.X[time_block, child, staff]
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
    for time_block in model.TIME_BLOCKS:
        for child in model.CHILDREN:
            model.junior_staff_constraints.add(
                expr=sum([
                        model.X[time_block, child, staff] 
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
    for staff in model.STAFF:
        time_range_req = [x for x in list(range(lunch_start, lunch_end))
                          if x in model.TIME_BLOCKS]
        if len(time_range_req) == 0:
            continue
        model.lunch_constraints.add(
                expr=sum(model.X[time_block, child, staff]
                         for time_block in time_range_req
                         for child in model.CHILDREN) <= span - 1
            )
    return model
