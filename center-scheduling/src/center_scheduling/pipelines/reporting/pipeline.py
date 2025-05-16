from kedro.pipeline import Pipeline, node, pipeline

from .nodes import *

def create_pipeline() -> Pipeline:
    # Define the pipeline
    return pipeline(
        [
            node(
                func = combine_outputs,
                inputs = [f"d{d}.solution_excel" for d in range(1, 6)],
                outputs = "solution_excel",
            ),
        ]
    )
