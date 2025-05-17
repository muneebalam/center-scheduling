import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)

def _24h_time_to_index(time: str) -> int:
    """
    Convert a 24-hour time string to an index.

    Args:
        time (str): Time in 24-hour format (e.g., "14:30").

    Returns:
        int: Index corresponding to the time.
    """
    #hour, minute, sec = map(int, str(time).split(':'))
    #return int(hour * 2 + minute / 30)
    if isinstance(time, pd.Timestamp):
        hr = time.hour
        minute = time.minute
        return int(hr * 2 + minute / 30)
    if isinstance(time, str):
        hr = int(time.split(':')[0])
        minute = int(time.split(':')[1])
        return int(hr * 2 + minute / 30)
    return time * 2


def _index_to_24h_time(index: int) -> str:
    """
    Convert an index to a 24-hour time string.

    Args:
        index (int): Index corresponding to the time.

    Returns:
        str: Time in 24-hour format (e.g., "14:30").
    """
    hour = int(index // 2)
    minute = int((index % 2) * 30)
    return f"{hour:02d}:{minute:02d}"

def setup_decision_variables(center_hours: pd.DataFrame, 
                             staff_child: pd.DataFrame,
                             absences: pd.DataFrame,
                             day: str) -> ConcreteModel:
    """
    Load center hours
    Load child x staff mapping
    Decision variables: Daily 30 min blocks: child x staff

    Args:
        center_hours (pd.DataFrame): DataFrame containing center hours.
        staff_child (pd.DataFrame): DataFrame containing staff-child relationships.
        day (str): The day for which the model is being set up.

    Returns:
        ConcreteModel: A Pyomo model object with the loaded data.
    """
    # Perform any necessary data processing or transformations here
    # For example, you might want to merge or filter the data

    model = ConcreteModel()
    model.CENTER_HOURS = center_hours.query(f"Day == '{day}'")
    model.STAFF_CHILD = staff_child
    model.ABSENCES = absences.pipe(lambda x: x[(x.Day.isna()) | (x.Day == day)])
    
    # Define the junior and senior staff
    model.JSTAFF = model.STAFF_CHILD.query("Role == 'Tech'")["Staff"].unique()
    model.SSTAFF = model.STAFF_CHILD.query("Role != 'Tech'")["Staff"].unique()

    # Create decision variables for the model
    model.CHILDREN = model.STAFF_CHILD.Child.unique()
    model.STAFF = model.STAFF_CHILD.Staff.unique()

    # Staff role todo
    model.DAYS = model.CENTER_HOURS.Day
    first_start = model.CENTER_HOURS.Open.min()
    last_end = model.CENTER_HOURS.Close.max()
    model.TIME_BLOCKS = range(_24h_time_to_index(first_start), 
                                  _24h_time_to_index(last_end))
    model.X = Var(model.DAYS, 
                  model.TIME_BLOCKS, 
                  model.CHILDREN,
                  model.STAFF,
                  within=Binary)

    # Return the processed data
    return model