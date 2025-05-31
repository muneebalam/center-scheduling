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
        else:
            start = _24h_time_to_index(start)
        if end is None or pd.isna(end):
            end = max(model.TIME_BLOCKS)
        else:
            end = _24h_time_to_index(end)

    # Also make sure these do not exceed time blocks
    start = max(start, min(model.TIME_BLOCKS))
    end = min(end, max(model.TIME_BLOCKS))
    return int(start), int(end)

def add_pto_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    if not constraint_on_off["pto"]:
        return model
    pto = model.ABSENCES.pipe(lambda x: x[x.Type == "pto"])[["Name", "Day", "Start", "End"]]
    for _, row in pto.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        df = model.INDEX_DF[(model.INDEX_DF["Time Block"] >= start) & (model.INDEX_DF["Time Block"] < end)]
        df = df[df["Staff"] == row["Name"]]
        for _, row in df.iterrows():
            model.X[row["Time Block"], row["Child"], row["Staff"]].fix(0)
    return model

def add_parent_training_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    if not constraint_on_off["parent_training"]:
        return model
    model.parent_training_constraints = ConstraintList()
    parent_training = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Parent Training"])[["Name", "Day", "Start", "End"]]
    for _, row in parent_training.iterrows():
        start, end = _clean_start_end(model, row)
        df = model.INDEX_DF[(model.INDEX_DF["Time Block"] >= start) & (model.INDEX_DF["Time Block"] < end)]
        df = df[df["Child"] == row["Name"]]
        for _, row in df.iterrows():
            model.X[row["Time Block"], row["Child"], row["Staff"]].fix(0)
    return model

def add_team_meeting_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    if not constraint_on_off["team_meeting"]:
        return model
    model.team_meeting_constraints = ConstraintList()
    team_meeting = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Team Meeting"])[["Name", "Day", "Start", "End"]]
    for _, row in team_meeting.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        df = model.INDEX_DF[(model.INDEX_DF["Time Block"] >= start) & (model.INDEX_DF["Time Block"] < end)]
        for _, row in df.iterrows():
            model.X[row["Time Block"], row["Child"], row["Staff"]].fix(0)
    return model

def add_nap_time_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    if not constraint_on_off["nap_time"]:
        return model
    model.nap_time_constraints = ConstraintList()
    nap_rows = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Nap"])[["Name", "Day", "Start", "End"]]
    for _, row in nap_rows.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        df = model.INDEX_DF[(model.INDEX_DF["Time Block"] >= start) & (model.INDEX_DF["Time Block"] < end)]
        df = df[df["Child"] == row["Name"]]
        for _, row in df.iterrows():
            model.X[row["Time Block"], row["Child"], row["Staff"]].fix(0)
    return model

def add_speech_therapy_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    if not constraint_on_off["speech_therapy"]:
        return model
    model.speech_constraints = ConstraintList()
    speech_therapy = model.ABSENCES.pipe(lambda x: x[x.Type.str.title() == "Speech"])[["Name", "Day", "Start", "End"]]
    for _, row in speech_therapy.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        df = model.INDEX_DF[(model.INDEX_DF["Time Block"] >= start) & (model.INDEX_DF["Time Block"] < end)]
        df = df[df["Child"] == row["Name"]]
        for _, row in df.iterrows():
            model.X[row["Time Block"], row["Child"], row["Staff"]].fix(0)
    return model

def add_arrival_departure_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    """
    Take kids who arrive late and leave early into account
    """
    if not constraint_on_off["arrival_departure"]:
        return model
    arr_dep = (
        model.ABSENCES
        .pipe(lambda x: x[x.Type.isin(["late arrival", "leaves early"])])
        [["Name", "Start", "End"]]
    )
    model.arrival_departure_constraints = ConstraintList()
    for _, row in arr_dep.iterrows():
        start, end = _clean_start_end(model, row)
        if start >= end:
            continue
        for i in range(start, end):
            df = model.INDEX_DF[(model.INDEX_DF["Time Block"] == i) & (model.INDEX_DF["Child"] == row["Name"])]
            for staff in df.Staff:
                model.X[i, row["Name"], staff].fix(0)

        #model.arrival_departure_constraints.add(
        #    expr=sum(model.X[i, row["Name"], staff]
        #             for staff in model.STAFF
        #             for i in range(start, end)) == 0
        #)
    return model

def center_hours_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    """
    Add constraints to ensure that the center is open during specified hours.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraints will be added.

    Returns:
        ConcreteModel: The model with the constraints added.
    """
    if not constraint_on_off["center_hours"]:
        return model
    model.center_hours_constraints = ConstraintList()
    for _, row in model.CENTER_HOURS.iterrows():
        day = row["Day"]
        start_time = _24h_time_to_index(row["Open"])
        end_time = _24h_time_to_index(row["Close"])
        for time_block, df in model.INDEX_DF.groupby("Time Block"):
            if time_block < start_time or time_block >= end_time:
                for _, row in df.iterrows():
                    model.X[time_block, row["Child"], row["Staff"]].fix(0)
    return model

def add_staff_child_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    if not constraint_on_off["staff_child"]:
        return model
    return model
    # model.staff_child_constraints = ConstraintList()
    # for child, staff_df in model.STAFF_CHILD.groupby("Child"):
    #     acceptable_staff = staff_df.Staff
    #     unacceptable_staff = model.STAFF[~pd.Series(model.STAFF).isin(acceptable_staff)]
    #     for staff in unacceptable_staff:
    #         for time_block in model.TIME_BLOCKS:
    #             # Add constraints to the model
    #             model.X[time_block, child, staff].fix(0)
    #             # model.staff_child_constraints.add(
    #             #     expr=model.X[time_block, child, staff] == 0
    #             # )
    # return model

def add_one_place_per_time_constraint(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    """
    Add a constraint to ensure that each staff is in one place at a time.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraint will be added.

    Returns:
        ConcreteModel: The model with the constraint added.
    """
    if not constraint_on_off["one_place_per_time"]:
        return model
    model.one_place_per_time = ConstraintList()
    for (time_block, staff), df in model.INDEX_DF.groupby(["Time Block", "Staff"]):
        model.one_place_per_time.add(
            expr=sum(model.X[time_block, child, staff]
                        for child in df.Child) <= 1
        )
    return model


def add_lunch_constraints(model: ConcreteModel, constraint_on_off: dict) -> ConcreteModel:
    """
    Add constraints to ensure that lunch is scheduled for each staff member between 12 and 2.

    Args:
        model (ConcreteModel): The Pyomo model to which the constraints will be added.

    Returns:
        ConcreteModel: The model with the constraints added.
    """
    if not constraint_on_off["lunch"]:
        return model
    # Define the lunch time range
    lunch_start = _24h_time_to_index(11.5)
    lunch_end = _24h_time_to_index(14)
    span = lunch_end - lunch_start

    model.lunch_constraints = ConstraintList()
    for staff, df in model.INDEX_DF.groupby("Staff"):
        time_range_req = [x for x in list(range(lunch_start, lunch_end))
                          if x in model.TIME_BLOCKS]
        if len(time_range_req) == 0:
            continue
        model.lunch_constraints.add(
                expr=sum(model.X[time_block, child, staff]
                         for time_block in time_range_req
                         for child in df.Child.unique()) <= span - 1
            )
    return model
