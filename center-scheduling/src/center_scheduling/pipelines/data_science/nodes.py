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
    hour, minute, sec = map(int, str(time).split(':'))
    return int(hour * 2 + minute / 30)
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

def setup_decision_variables(center_hours: pd.DataFrame, staff_child: pd.DataFrame) -> ConcreteModel:
    """
    Load center hours
    Load child x staff mapping
    Decision variables: Daily 30 min blocks: child x staff

    Args:
        center_hours (pd.DataFrame): DataFrame containing center hours.
        staff_child (pd.DataFrame): DataFrame containing staff-child relationships.

    Returns:
        ConcreteModel: A Pyomo model object with the loaded data.
    """
    # Perform any necessary data processing or transformations here
    # For example, you might want to merge or filter the data

    model = ConcreteModel()
    model.CENTER_HOURS = center_hours
    model.STAFF_CHILD = staff_child

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
            # Add constraints to the model
            model.lunch_constraints.add(
                expr=sum(model.X[day, time_block, child, staff]
                         for time_block in range(lunch_start, lunch_end)
                         for child in model.CHILDREN) <= span - 1
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

# Objective and solve -----------------------------------------------------------------

def add_objective(model: ConcreteModel) -> ConcreteModel:
    """
    Add an objective function to the model.

    Args:
        model (ConcreteModel): The Pyomo model to which the objective will be added.

    Returns:
        ConcreteModel: The model with the objective function added.
    """
    # Define the objective function
    # Maximize child hours - preference to techs though
    child_jstaff_hrs = sum([model.X[day, time_block, child, staff]
                                          for day in model.DAYS
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN
                                          for staff in model.JSTAFF])
    child_sstaff_hrs = sum([model.X[day, time_block, child, staff]
                                          for day in model.DAYS
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN
                                          for staff in model.SSTAFF])
    # Penalize when children do not have staff
    child_no_staff_hrs = sum([model.z_child_no_staff[day, time_block, child]
                                          for day in model.DAYS
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN])
    
    # Penalize when children have two staff
    child_2_staff_hrs = sum([model.z_child_2_staff_hrs[day, time_block, child]
                                          for day in model.DAYS
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN])
    # Penalize switches
    child_switch_hrs = sum([model.z_switch[day, time_block, staff]
                                          for day in model.DAYS
                                          for time_block in model.TIME_BLOCKS
                                          for staff in model.STAFF])

                    
    model.objective = Objective(expr=child_jstaff_hrs
                                + child_sstaff_hrs * 0.5 
                                - child_no_staff_hrs 
                                - child_2_staff_hrs
                                - child_switch_hrs * 0.1, 
                                sense=maximize)
    return model

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
    )
    # Go in order of days
    final_res = pd.concat([
        results_df_wide
        .pipe(lambda x: x[x.Day == d])
        .sort_values("Time Block")
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]
    ]).assign(**{"Time Block": lambda x: x["Time Block"].apply(_index_to_24h_time)})
    return final_res