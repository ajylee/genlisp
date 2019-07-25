from genlisp.base import *
import json
from pathlib import Path
import enum
from typing import Set, Union, Any, List, Optional, Tuple, Dict, FrozenSet
import random
from genlisp.game import (ExpressionPlan, ComponentReference, Sketch, compile_expression_plan, CoinFlippingAgent, Game,
                          randomly_named_variable, compile_sketch)
import attr


def is_atomic(item):
    if isinstance(item, (Let, Lambda, Beta, If)):
        return False
    elif item is evaluate:
        return False
    else:
        return True


def main():
    _agent = CoinFlippingAgent()
    game = Game(sketch=Sketch(), max_turns=200)
    sketch = _agent.play(game)
    compiled_expressions, well_formed_expressions = compile_sketch(sketch)
    print('score:', game.score())

    import pprint
    pprint.pprint(well_formed_expressions)


if __name__ == '__main__':
    main()

    ss = {Let, randomly_named_variable()}
