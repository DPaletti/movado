from collections import OrderedDict
from typing import List, Callable

from movado.controller import Controller
from movado.estimator import Estimator
from functools import wraps
from movado.distance_controller import DistanceController
from movado.hoeffding_adaptive_tree_model import HoeffdingAdaptiveTreeModel
from movado.chained_estimator import ChainedEstimator
import movado.movado_static


# This imports are unused but populate the global symbol table for the globals() call
# noinspection PyUnresolvedReferences
from movado.mab_controller import MabController  # pylint: disable=unused-import

# noinspection PyUnresolvedReferences
from movado.voting_controller import VotingController  # pylint: disable=unused-import

# noinspection PyUnresolvedReferences
from movado.kernel_regression_model import (
    KernelRegressionModel,
)  # pylint: disable=unused-import


def approximate(
    **kwargs,
) -> Callable[
    [Callable[[List[float]], List[float]]], Callable[[List[float]], List[float]]
]:
    def approximate_decorator(
        func: Callable[[List[float]], List[float]]
    ) -> Callable[[List[float]], List[float]]:
        controller: Controller
        estimator: Estimator
        is_first_call: bool = True

        @wraps(func)
        def wrapper(*wrapper_args) -> List[float]:
            # args must either contain the point to be analyzed
            # or it must contain self (for class methods) and then the point
            nonlocal is_first_call
            nonlocal controller
            nonlocal estimator
            if len(wrapper_args) < 1 or len(wrapper_args) > 2:
                raise Exception(
                    "The decorated function must have a single input which is a list of numbers, "
                    + "self may also be present for non-static class methods, in such case self is "
                    + "expected to be the first argument followed by the point and nothing"
                )
            if len(wrapper_args) == 1:
                point = wrapper_args[0]
            else:
                point = wrapper_args[1]
            if is_first_call:
                is_first_call = False
                selected_model = globals().get(str(kwargs.get("estimator")) + "Model")
                model = (
                    HoeffdingAdaptiveTreeModel if not selected_model else selected_model
                )
                # TODO add multi-output non-chained estimators
                outputs: int = kwargs.get("outputs")
                if not outputs:
                    raise Exception(
                        "Please specify outputs as a kwarg as the number of targets of the fitness function"
                    )
                estimator = ChainedEstimator(
                    model(
                        **{
                            k[k.find("_") + 1 :]: v
                            for k, v in kwargs.items()
                            if k[: k.find("_")] == "estimator"
                        }
                    ),
                    outputs,
                )
                selected_controller = globals().get(
                    str(kwargs.get("controller")) + "Controller"
                )
                controller = (
                    DistanceController
                    if not selected_controller
                    else selected_controller
                )
                if selected_controller is MabController:
                    params = OrderedDict(
                        {
                            "cover": [3, 5, 7, 11, 20],
                            "mab_weight_epsilon": [0.1, 0.2, 0.3, 0.4],
                            "mab_weight_bandwidth": [1, 5, 10, 20, 50, 75],
                        }
                    )
                else:
                    # All other cases are handled as a DistanceController
                    params = OrderedDict(
                        {
                            "nth_nearest": [1, 3, 5, 7],
                            "mab_epsilon": [0.1, 0.2, 0.3],
                            "mab_bandwidth": [1, 5, 10, 20],
                            "mab_weight_epsilon": [0.1, 0.2, 0.3],
                            "mab_weight_bandwidth": [1, 5, 10, 20],
                        }
                    )
                controller = VotingController(
                    controller,
                    estimator,
                    func,
                    params,
                    self_exact=None if len(wrapper_args) == 1 else wrapper_args[0],
                    **{
                        k[k.find("_") + 1 :]: v
                        for k, v in kwargs.items()
                        if k[: k.find("_")] == "controller"
                    },
                )

            return list(
                controller.compute_objective(point)
            )  # we expect the first and only argument of the function to be the input point

        if kwargs.get("disabled"):
            return func
        return wrapper

    return approximate_decorator
