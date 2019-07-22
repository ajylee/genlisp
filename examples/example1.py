from genlisp.base import *
import json
from pathlib import Path
import enum
from typing import Set, Union, Any, List, Optional, Tuple, Dict, FrozenSet
import random
from genlisp.game import ExpressionPlan, ComponentReference
from genlisp.immutables import ImmutableMap

import attr


class SimpleChoice(enum.Enum):
    new_auto_named_variable = enum.auto()
    new_literal = enum.auto()
    finish = enum.auto()


@attr.s(frozen=True, auto_attribs=True)
class NewCompoundExpression:
    type_: type


@attr.s(frozen=True, auto_attribs=True)
class ConnectionChoice:
    slot: ComponentReference
    plugs: Tuple[Any, ...]


@attr.s(frozen=True, auto_attribs=True)
class NewLiteralChoice:
    value: Any


CodeChoice = Union[NewLiteralChoice, ConnectionChoice, NewCompoundExpression, SimpleChoice]


expression_heads = (Let, Lambda, Beta, If)


# Options:

# 1. create new thing
# 2. make a connection between two things

class Sketch:
    unfinished_expressions: List
    finished_expressions: List
    expression_plans: List
    literals: List
    variables: List

    new_expression_choices = frozenset([
        NewCompoundExpression(Let),
        NewCompoundExpression(Lambda),
        NewCompoundExpression(Beta),
        NewCompoundExpression(If),
        SimpleChoice.new_auto_named_variable,
    ])

    def __init__(self):
        self.unfinished_expressions = []
        self.finished_expressions = []
        self.literals = [True, False]
        self.variables = []
        self.variable_bindings = {}

    @staticmethod
    def connection_slot_choice(context: ExpressionPlan) -> List[ComponentReference]:
        """
        Give choice to start a new expression or connect pieces of existing one
        """
        _metadata: ExpressionModel = expression_models[context.head]
        components: List[ComponentMetadata] = [c for c in _metadata.components.values() if
                                               c.name not in ['closed', 'name']]
        return [ComponentReference(context, [c.name]) for c in components]

    def connection_plug_choice(self, slot: ComponentReference) -> List[List[Union[Expression, ExpressionPlan]]]:
        _expression_model: ExpressionModel = expression_models[slot.base.head]
        component_metadata: ComponentMetadata = _expression_model.components[slot.attr_chain[0]]
        if component_metadata.typing_ == VariableTuple:
            return [[v for v in self.variables if v not in self.variable_bindings]]
        elif component_metadata.typing_ == VariableMapping:
            return [[v for v in self.variables if v not in self.variable_bindings],
                    list(chain(self.variables, self.literals, self.unfinished_expressions, self.finished_expressions))]
        elif component_metadata.typing_ == GenLispCallable:
            return [[x for x in chain(self.unfinished_expressions, self.finished_expressions, self.literals)
                     if (isinstance(x, GenLispCallable.args) or
                         (isinstance(x, ExpressionPlan) and x.head in GenLispCallable.args))
                     ] + list(self.variables)]
        else:
            return [list(chain(self.variables, self.literals, self.unfinished_expressions, self.finished_expressions))]

    def update(self, choice: CodeChoice):
        if isinstance(choice, NewCompoundExpression):
            iex = ExpressionPlan(head=choice.type_)

            _expression_model: ExpressionModel = expression_models[iex.head]
            for _component_metadata in _expression_model.components.values():
                if _component_metadata.init is not None:
                    iex.parts[_component_metadata.name] = _component_metadata.init()
                elif _component_metadata.typing_ is str:
                    iex.parts[_component_metadata.name] = random.choice(canned_names).lower()

            assert not isinstance(iex.head, ExpressionPlan)
            self.unfinished_expressions.append(iex)
        elif isinstance(choice, ConnectionChoice):
            ref: ComponentReference = choice.slot
            # print(ref.base, ref.attr_chain)
            assert isinstance(ref, ComponentReference)
            assert isinstance(ref.base, ExpressionPlan)

            _component_metadata = expression_models[ref.base.head].components[ref.attr_chain[0]]
            if _component_metadata.typing_ is Expression:
                ref.base.parts[ref.attr_chain[0]] = choice.plugs[0]
            elif _component_metadata.typing_ is VariableTuple:
                variables = choice.plugs
                ref.base.parts[ref.attr_chain[0]] += tuple(variables)
                for vv in variables:
                    self.variable_bindings[vv] = ref.base
            elif _component_metadata.typing_ is VariableMapping:
                k, v = choice.plugs
                ref.base.parts[ref.attr_chain[0]][k] = v

            if expression_models[ref.base.head].required_components() <= set(ref.base.parts.keys()):
                if ref.base.head == Beta:
                    ok = (not ref.base.parts['head'] in GenLispCallable.args or
                          set(ref.base.parts['head'].variables) <= set(ref.base.parts['kwargs']))
                else:
                    ok = True

                if ok:
                    self.finished_expressions.append(ref.base)
                    self.unfinished_expressions.remove(ref.base)
                    ref.base.finished = True

        elif isinstance(choice, SimpleChoice):
            if choice == SimpleChoice.new_auto_named_variable:
                self.variables.append(randomly_named_variable())
        elif isinstance(choice, NewLiteralChoice):
            raise NotImplementedError


class LimitedSketch(Sketch):
    new_expression_choices = frozenset([
        NewCompoundExpression(Beta),
        NewCompoundExpression(Lambda),
        SimpleChoice.new_auto_named_variable,
    ])

    def __init__(self):
        super().__init__()
        self.finished_expressions.append(Nand)


class Agent(abc.ABC):
    @abc.abstractmethod
    def choice(self, sketch: Sketch) -> CodeChoice:
        pass

    def play(self, game: 'Game'):
        for ii in range(game.max_turns):
            choice: CodeChoice = self.choice(game.sketch)
            if choice == SimpleChoice.finish:
                return game.sketch
            else:
                game.sketch.update(choice)

        else:
            print('ran out of moves')
            return game.sketch


@attr.s(auto_attribs=True)
class Game:
    sketch: Sketch
    max_turns: int

    def score(self):
        compiled_expressions, well_formed_expressions = compile_sketch(self.sketch)
        return len(well_formed_expressions)


class CoinFlippingAgent(Agent):
    def choice(self, sketch: Sketch) -> CodeChoice:
        while True:
            if (not sketch.unfinished_expressions and sketch.finished_expressions
                    and random.choice(range(100)) < 70):
                return SimpleChoice.finish
            elif sketch.unfinished_expressions and random.choice(range(100)) < 80:
                # pick a context, then a thing to connect to
                context = random.choice(sketch.unfinished_expressions)
                slot = random.choice(sketch.connection_slot_choice(context))

                _metadata: ExpressionModel = expression_models[slot.base.head]
                component_metadata: ComponentMetadata = _metadata.components[slot.attr_chain[0]]

                plug_choices_collection = sketch.connection_plug_choice(slot)
                if not plug_choices_collection:
                    continue

                plugs = ()

                for plug_choices in plug_choices_collection:
                    if not plug_choices:
                        break
                    plugs += (random.choice(plug_choices),)
                else:
                    if component_metadata.typing_ is VariableMapping:
                        assert len(plugs) == 2

                    return ConnectionChoice(slot=slot, plugs=plugs)
            else:
                choices = sketch.new_expression_choices
                return random.choice(list(choices))


# set up random names
try:
    with Path('~/.config/genlisp/names.json').expanduser().open() as fp:
        canned_names = json.load(fp)
    for name in canned_names:
        assert isinstance(name, str)
except (FileNotFoundError, json.JSONDecodeError):
    canned_names = ['acorn', 'banana', 'cat', 'phobos']


def randomly_named_variable():
    import random
    _name = random.choice(canned_names).lower()
    return Variable(_name)


def is_atomic(item):
    if isinstance(item, (Let, Lambda, Beta, If)):
        return False
    elif item is evaluate:
        return False
    else:
        return True


def compile_expression_plan(expression_plan: Union[ExpressionPlan, Expression],
                            expressions: Dict[ExpressionPlan, Tuple[Optional[Expression], bool]],
                            trace: Set[ExpressionPlan],
                            unfinished_expressions: FrozenSet[ExpressionPlan]) \
        -> Tuple[Optional[Expression], bool]:
    """

    :param expression_plan:
    :param expressions:
    :param trace:
    :param unfinished_expressions:
    :return: compiled expression, whether well formed.
    """

    if expression_plan in trace or expression_plan in unfinished_expressions:
        return None, False

    try:
        return expressions[expression_plan]
    except KeyError:
        pass

    if isinstance(expression_plan, ExpressionPlan):
        trace.add(expression_plan)
        compiled_parts = {}
        _expression_model = expression_models[expression_plan.head]

        top_is_well_formed = True

        for component_name, component_value in expression_plan.parts.items():
            component_metadata = _expression_model.components[component_name]
            if component_metadata.typing_ in (Expression, Lambda):
                compiled_parts[component_name], component_well_formed = (
                    compile_expression_plan(component_value, expressions,
                                            trace, unfinished_expressions))
            elif component_metadata.typing_ == VariableMapping:
                compilation_results = {
                    kk: compile_expression_plan(vv, expressions, trace, unfinished_expressions)
                    for kk, vv in component_value.items()}
                compiled_parts[component_name] = ImmutableMap({kk: vv[0] for kk, vv in compilation_results.items()})
                component_well_formed = all(vv[1] for vv in compilation_results.values())
            elif component_metadata.typing_ == VariableTuple:
                compiled_parts[component_name] = component_value
                component_well_formed = all(isinstance(vv, Variable) for vv in component_value)
            else:
                compiled_parts[component_name] = component_value
                component_well_formed = isinstance(component_value, component_metadata.typing_)
                # raise TypeError("Unrecognized component type: {}".format(component_metadata.typing_))

            top_is_well_formed = top_is_well_formed and component_well_formed

        expression = expression_plan.head(**compiled_parts)
        expressions[expression_plan] = expression, top_is_well_formed
        trace.remove(expression_plan)
        return expression, top_is_well_formed
    else:
        return expression_plan, True


def compile_sketch(sketch: Sketch):
    # 1. figure out how many "islands" there are
    #

    expressions = {}
    visited = set()

    for expression_plan in sketch.finished_expressions:  # type: ExpressionPlan
        compile_expression_plan(expression_plan, expressions, visited,
                                frozenset(sketch.unfinished_expressions))

    well_formed_expressions = []
    for (expression, well_formed) in expressions.values():
        if well_formed:
            well_formed_expressions.append(expression)

    return expressions, well_formed_expressions


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
