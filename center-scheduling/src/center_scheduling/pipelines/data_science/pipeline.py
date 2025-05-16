from kedro.pipeline import Pipeline, node, pipeline

from .nodes import (
    setup_decision_variables, 
    add_staff_child_constraints,
    solve,
    add_objective,
    print_solution,
    add_one_place_per_time_constraint,
    add_child_no_staff_indicator,
    center_hours_constraints,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            # Data
            node(
                func = setup_decision_variables,
                inputs = ["center_hours", "staff_child"],
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
            ## Lunch
            ## Nap time
            ## Up to 1 senior staff per child per 30min (TBC)
            ## Each staff and child in one place at a time
            node(
                func = add_one_place_per_time_constraint,
                inputs = "model_c1",
                outputs = "model_c2",
            ),
            
            ## Unavailability: Staff training, PTO, Parent training, Team meeting
            ## Remote day: can be a second on a child, not the only one

            ## Indicators
            node(
                func = add_child_no_staff_indicator,
                inputs = "model_c2",
                outputs = "model_c3",
            ),

            # Objective: Maximize child-staff hours
            node(
                func = add_objective,
                inputs = "model_c3",
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
            )
        ]
    )
