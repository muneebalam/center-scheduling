from kedro.pipeline import Pipeline, node, pipeline

from .nodes import *

def _base_opt_pipeline(day: int) -> Pipeline:
    """
    Base pipeline for the optimization of the center schedule.
    """

    # Define the pipeline
    return pipeline(
        [
            # Data
            node(
                func = setup_decision_variables,
                inputs = ["center_hours", "staff_child", "params:day"],
                outputs = "base_model",
            ),

            # Constraints
            ## Center hours
            node(
                func = center_hours_constraints,
                inputs = "base_model",
                outputs = "model_c0",
            ),
            ## Staff x child matching
            node(
                func = add_staff_child_constraints,
                inputs = "model_c0",
                outputs = "model_c1",
            ),
            ## Assessments (TBC)
            ## 1:1 trainings (TBC)
            ## Admin (TBC)
            ## Nap time
            ## Up to 1 senior staff per child per 30min (TBC)
            ## Each staff and child in one place at a time
            node(
                func = add_one_place_per_time_constraint,
                inputs = "model_c1",
                outputs = "model_c2",
            ),
            ## Lunch
            node(
                func = add_lunch_constraints,
                inputs = "model_c2",
                outputs = "model_c3",
            ),
            ## At most one junior staff per child
            node(
                func = add_junior_staff_constraints,
                inputs = "model_c3",
                outputs = "model_c4",
            ),
            
            ## Unavailability: Staff training, PTO, Parent training, Team meeting
            ## Remote day: can be a second on a child, not the only one
            ## Restrictions - e.g. staff training on a kid

            

            ## Indicators
            node(
                func = add_child_no_staff_indicator,
                inputs = "model_c4",
                outputs = "model_c5",
            ),
            node(
                func = add_staff_not_fully_used_indicator,
                inputs = "model_c5",
                outputs = "model_c6",
            ),
            node(
                func = add_child_2_staff_indicator,
                inputs = "model_c6",
                outputs = "model_c7",
            ),
            node(
                func = add_switch_indicator,
                inputs= "model_c7",
                outputs = "model_c8",
            ),

            # Objective: Maximize child-staff hours
            node(
                func = add_objective,
                inputs = "model_c8",
                outputs = "model_obj",
            ),

            # Solve
            node(
                func=solve,
                inputs = "model_obj",
                outputs = "model_solved",
            ),
            node(
                func=print_solution,
                inputs = "model_solved",
                outputs = "solution_excel",
            ),
        ],
        parameters={"params:day": f"params:day{day}"},
        inputs = {c: c for c in ["center_hours", "staff_child"]},
        namespace=f"d{day}",
    )

def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([_base_opt_pipeline(day=d) for d in range(1, 6)])