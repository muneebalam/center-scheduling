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
                inputs = ["center_hours", "staff_child", "absences","roles","params:day"],
                outputs = "base_model",
            ),
            node(
                func = input_sense_checks,
                inputs = "base_model",
                outputs = "base_model_checked",
            ),
            node(
                func=save_model_index,
                inputs="base_model_checked",
                outputs="model_index",
            ),

            # Constraints
            ## Center hours
            node(
                func = center_hours_constraints,
                inputs = ["base_model", "params:constraint_on_off"],
                outputs = "model_c0",
            ),
            ## Staff x child matching
            node(
                func = add_staff_child_constraints,
                inputs = ["model_c0", "params:constraint_on_off"],
                outputs = "model_c1",
            ),
            ## Assessments (TBC)
            ## 1:1 trainings (TBC)
            ## Admin (TBC)
            ## Each staff and child in one place at a time
            node(
                func = add_one_place_per_time_constraint,
                inputs = ["model_c1", "params:constraint_on_off"],
                outputs = "model_c2",
            ),
            ## Lunch
            node(
                func = add_lunch_constraints,
                inputs = ["model_c2", "params:constraint_on_off"],
                outputs = "model_c3",
            ),
            ## PTO
            node(
                func = add_pto_constraints,
                inputs = ["model_c3", "params:constraint_on_off"],
                outputs = "model_c42",
            ),
            ## Parent training
            node(
                func = add_parent_training_constraints,
                inputs = ["model_c42", "params:constraint_on_off"],
                outputs = "model_c43",
            ),
            ## Team meeting
            node(
                func = add_team_meeting_constraints,
                inputs = ["model_c43", "params:constraint_on_off"],
                outputs = "model_c44",
            ),
            ## Nap
            node(
                func = add_nap_time_constraints,
                inputs = ["model_c44", "params:constraint_on_off"],
                outputs = "model_c45",
            ),
            ## Therapy
            node(
                func = add_speech_therapy_constraints,
                inputs = ["model_c45", "params:constraint_on_off"],
                outputs = "model_c46",
            ),
            ## Late arrivals, early departures
            node(
                func = add_arrival_departure_constraints,
                inputs = ["model_c46", "params:constraint_on_off"],
                outputs = "model_c47",
            ),
            
            ## Unavailability: Staff training, PTO, Parent training, remote, Team meeting

            ## Indicators
            node(
                func = add_child_2_staff_indicator,
                inputs = "model_c47",
                outputs = "model_c5",
            ),
            node(
                func = add_switch_indicator,
                inputs= "model_c5",
                outputs = "model_c8",
            ),

            # Objective: Maximize child-staff hours
            node(
                func = add_objective,
                inputs = ["model_c8", "params:reward_for_child_staff_role"],
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
        parameters={"params:day": f"params:day{day}",
                    **{c: c for c in ["params:reward_for_child_staff_role", "params:constraint_on_off"]}},
        inputs = {c: c for c in ["center_hours", "staff_child", "absences","roles"]},
        namespace=f"d{day}",
    )

def create_pipeline(**kwargs) -> Pipeline:
    myrange = range(1, 6)
    return pipeline([_base_opt_pipeline(day=d) for d in myrange])