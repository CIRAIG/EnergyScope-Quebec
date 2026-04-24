from energyscope.models import Model
from energyscope.energyscope import Energyscope
from energyscope.result import postprocessing, Result

def run_model(
        model: Model,
) -> Result:
    solver_options = {
        'solver': 'gurobi',
        'solver_msg': 0,
    }

    es = Energyscope(model=model, solver_options=solver_options)
    res = es.calc()
    res = postprocessing(res)

    return res