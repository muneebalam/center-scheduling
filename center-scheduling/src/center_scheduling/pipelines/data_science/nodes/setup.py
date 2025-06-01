import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)

def _clean_names(names: pd.Series) -> pd.Series:
    return names.str.strip().str.replace(" ", "").str.replace("_", "")

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
    try:
        time = float(time)
        return int(time * 2)
    except ValueError:
        pass
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

def _add_sbt_ts_bs_to_staff_child(staff_child: pd.DataFrame, roles: pd.DataFrame) -> pd.DataFrame:
    """
    Add SBT, TS, and BS to staff_child long matrix.
    """
    sbt_ts_bs = roles.pipe(lambda x: x[x.Role.isin(["SBT", "TS", "BS"])]).Name
    unique_children = staff_child.Child.unique()
    return pd.concat([
        staff_child,
        *[pd.DataFrame({
            "Child": unique_children,
            "Staff": s,
        }) for s in sbt_ts_bs]
    ])
    

def setup_decision_variables(center_hours: pd.DataFrame, 
                             staff_child: pd.DataFrame,
                             absences: pd.DataFrame,
                             roles: pd.DataFrame,
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
    model.STAFF_CHILD_MATRIX = staff_child
    model.STAFF_CHILD = (
        staff_child
        .melt(id_vars="Child", var_name="Staff", value_name="Allowed")
        .pipe(lambda x: x[x.Allowed != ''])
        .pipe(lambda x: x[~x.Allowed.isna()])
        .assign(Child = lambda x: _clean_names(x.Child),
        Staff = lambda x: _clean_names(x.Staff))
        .drop(columns="Allowed")
    )
    
    model.ABSENCES = (
        absences.pipe(lambda x: x[(x.Day.isna()) | (x.Day == day)])
        .assign(Type = lambda x: x.Type.str.strip().str.lower(),
               Name = lambda x: _clean_names(x.Name))
    )
    model.ROLES = roles.assign(Name = lambda x: _clean_names(x.Name))
    model.STAFF_CHILD = (
        _add_sbt_ts_bs_to_staff_child(model.STAFF_CHILD, model.ROLES)
        .assign(Staff = lambda x: _clean_names(x.Staff))
    )
    
    # Define the junior and senior staff
    model.JSTAFF = model.ROLES.pipe(lambda x: x[x.Role.isin(["Tech", "SBT"])])["Name"]
    model.SSTAFF = model.ROLES.pipe(lambda x: x[~x.Role.isin(["Tech", "SBT"])])["Name"]
    # Filter to make sure they should be scheduled
    model.JSTAFF = [x for x in model.JSTAFF if x in model.STAFF_CHILD.Staff.unique()]
    model.SSTAFF = [x for x in model.SSTAFF if x in model.STAFF_CHILD.Staff.unique()]

    # Create decision variables for the model
    model.DAY = model.CENTER_HOURS.Day.iloc[0]
    first_start = model.CENTER_HOURS.Open.min()
    last_end = model.CENTER_HOURS.Close.max()
    model.TIME_BLOCKS = range(_24h_time_to_index(first_start), 
                                  _24h_time_to_index(last_end))
    
    # Create a list of valid (time, child, staff) combinations based on staff_child relationships
    valid_combinations = []
    for time in model.TIME_BLOCKS:
        for _, row in model.STAFF_CHILD.iterrows():
            valid_combinations.append((time, row['Child'], row['Staff']))
    
    model.X = Var(valid_combinations, within=Binary)
    model.INDEX_DF = pd.DataFrame.from_records(model.X.keys(), columns=["Time Block", "Child", "Staff"])
    
    # Return the processed data
    return model

def save_model_index(model: ConcreteModel) -> pd.DataFrame:
    return model.INDEX_DF
                    
def input_sense_checks(model: ConcreteModel) -> ConcreteModel:
    """Checks:
    
    1. All names in staff_child matrix are in roles
    """
    names_in_matrix_not_roles = {c for c in set(model.STAFF_CHILD.Staff) if c not in set(model.ROLES.Name)}
    assert len(names_in_matrix_not_roles) == 0, f"Names in staff_child matrix not in roles: {names_in_matrix_not_roles}"
    return model