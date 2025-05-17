import logging
logger = logging.getLogger(__name__)

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
        relevant_staff = [x for x in relevant_staff if x in model.STAFF]
        if len(relevant_staff) > 0:
            child_hr_objs[role] = sum([model.X[time_block, child, staff]
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN
                                          for staff in relevant_staff]) * reward

    # Penalize when children do not have staff
    # may not be needed since obj maximizes children having staff
   # child_no_staff_hrs = sum([model.z_child_no_staff[time_block, child]
   #                                       for time_block in model.TIME_BLOCKS
   #                                       for child in model.CHILDREN])
    
    # Penalize when children have two staff
    child_2_staff_hrs = sum([model.z_child_2_staff_hrs[time_block, child]
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN])
    # Penalize switches
    child_switch_hrs = sum([model.z_switch[time_block, staff]
                                          for time_block in model.TIME_BLOCKS
                                          for staff in model.STAFF])

                    
    model.objective = Objective(expr=sum(child_hr_objs.values())
                                - child_2_staff_hrs
                                - child_switch_hrs * 0.1, 
                                sense=maximize)
    return model