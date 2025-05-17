import logging
logger = logging.getLogger(__name__)

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, SolverFactory, Set, Binary,
    ConstraintList, maximize
)



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
    child_jstaff_hrs = sum([model.X[time_block, child, staff]
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN
                                          for staff in model.JSTAFF])
    child_sstaff_hrs = sum([model.X[time_block, child, staff]
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN
                                          for staff in model.SSTAFF])
    # Penalize when children do not have staff
    child_no_staff_hrs = sum([model.z_child_no_staff[time_block, child]
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN])
    
    # Penalize when children have two staff
    child_2_staff_hrs = sum([model.z_child_2_staff_hrs[time_block, child]
                                          for time_block in model.TIME_BLOCKS
                                          for child in model.CHILDREN])
    # Penalize switches
    child_switch_hrs = sum([model.z_switch[time_block, staff]
                                          for time_block in model.TIME_BLOCKS
                                          for staff in model.STAFF])

                    
    model.objective = Objective(expr=child_jstaff_hrs
                                + child_sstaff_hrs * 0.5 
                                - child_no_staff_hrs 
                                - child_2_staff_hrs
                                - child_switch_hrs * 0.1, 
                                sense=maximize)
    return model