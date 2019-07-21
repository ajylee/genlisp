"""
Simple Untyped Lambda Calculus

Note that the scoping is a mix of lexical and dynamic. Since this is not meant
for humans, if one wants to maintain lexical scope, one simply generates new
variables where a dynamic variable shadowing would otherwise occur. Below I use
python-esk pseudocode for readability.

For example in::

    (let ((a 1))
        (let ((f1 (lambda () a))
              (f2 (lambda () (f1)))
              (f3 (lambda () (let ((a 2)) (f2))))))
              (f3))  ;; -> 2

Alternatively::

    def f1():
        return a

    def f2():
        return f1()

    def f3():
        let a = 2
        return f2()

    f3()  # -> 2

With dynamic scoping, `f3() -> 2`, but we could just require that a new variable
be used on every variable declaration, so variables are "single use".
Then shadowing only occurs with recursion.

Note that the closing-over of variables occurs when a Lambda escapes its parent scope::

    def f1():
        a = 2
        def f2():
            return a

    a = 3
    f1() # -> 2

Therefore, if the "closing over" has occurred, scoping becomes lexical.

"""

from typing import Union, Mapping, Optional, Any, List, Tuple, TypeVar
import typing
import abc
import attr
from uuid import uuid4, UUID
from itertools import chain
from .frozendict import frozendict

# abuse Union as Intersection until Intersection is supported
# Union fools the type checker just enough to behave acceptably as a stand-in for
# Intersection
Intersection = Union

BaseType = Union[bool]


class CompoundExpression(abc.ABC):
    pass


@attr.s(frozen=True, repr=False)
class Token(CompoundExpression):
    name: str = attr.ib(hash=True)

    def __repr__(self):
        return self.name


@attr.s(frozen=True, repr=False)
class FunctionToken(Token):
    variables: Tuple['Variable', ...] = attr.ib(hash=True)


# Expression includes Lambda and Beta
Expression = Union[Token, BaseType, CompoundExpression]


class Variable:
    uuid: UUID
    name: str

    def __init__(self, name='_'):
        self.uuid = uuid4()
        self.name = name

    def __hash__(self):
        return hash(self.uuid)

    def __repr__(self):
        return self.name


@attr.s(auto_attribs=True)
class Lambda(CompoundExpression):
    variables: Tuple[Variable, ...] = attr.ib()
    body: Expression = attr.ib()
    closed: Mapping[Variable, Expression] = attr.ib(factory=frozendict, converter=frozendict)
    name: str = attr.ib(default=None)


@attr.s(auto_attribs=True)
class Beta(CompoundExpression):
    head: Union[Expression] = attr.ib()  # must return callable type
    args: Tuple[Expression, ...] = attr.ib(factory=tuple)
    kwargs: Mapping[Variable, Expression] = attr.ib(factory=frozendict, converter=frozendict)


@attr.s(auto_attribs=True)
class If(CompoundExpression):
    condition: Expression = attr.ib()
    if_clause: Expression = attr.ib()
    else_clause: Expression = attr.ib()


@attr.s(auto_attribs=True)
class Let(CompoundExpression):
    mapping: Mapping[Variable, Expression] = attr.ib(converter=frozendict)
    body: Expression = attr.ib()
    closed: Mapping[Variable, Expression] = attr.ib(factory=frozendict, converter=frozendict)
    # recur: typing.Optional[Variable] = attr.ib(default=None)


@attr.s(auto_attribs=True)
class ExpressionModel:
    subject: typing.Callable[[Any], Expression]
    components: Mapping

    def required_components(self):
        return frozenset(
            c.name for c in self.components.values() if c.required
        )

    @staticmethod
    def from_subject_and_component_list(subject, components: List['ComponentMetadata']) -> 'ExpressionModel':
        em = ExpressionModel(subject=subject,
                             components={cc.name: cc for cc in components})
        for cc in components:
            cc.parent = em

        return em


@attr.s(auto_attribs=True)
class InspectableType:
    """Python `typing` annotations do not allow inspection. Use this instead.

    See also https://stackoverflow.com/questions/53854463/python-3-7-check-if-type-annotation-is-subclass-of-generic
    """
    typing_base: TypeVar
    args: Tuple[Union['InspectableType', type], ...]

    def to_type_hint(self):
        args_to_type_hint = tuple(
            a.to_type_hint if isinstance(a, InspectableType) else a
            for a in self.args)
        return self.typing_base[args_to_type_hint]


VariableMapping = InspectableType(Mapping, (Variable, Expression))
VariableTuple = InspectableType(Tuple, (Variable,))
GenLispCallable = InspectableType(Union, (Lambda, FunctionToken))


@attr.s(auto_attribs=True)
class ComponentMetadata:
    name: str
    typing_: Union[InspectableType, type]  # typing.Generic
    parent: Optional[ExpressionModel] = None
    required: bool = False
    init: Any = None


expression_models = {
    exm.subject: exm for exm in [
        ExpressionModel.from_subject_and_component_list(
            subject=Lambda,
            components=[
                ComponentMetadata(name='variables', typing_=VariableTuple, required=True, init=tuple),
                ComponentMetadata(name='body', typing_=Expression, required=True),
                # ComponentMetadata(name='closed', typing_=typing.Mapping[Variable, Expression]),
                ComponentMetadata(name='name', typing_=str),
            ]),
        ExpressionModel.from_subject_and_component_list(
            subject=Beta,
            components=[
                ComponentMetadata(name='head', typing_=Lambda, required=True),
                # ComponentMetadata(name='args', typing_=typing.Tuple[Expression, ...]),
                ComponentMetadata(name='kwargs', typing_=VariableMapping, init=dict)
            ]),
        ExpressionModel.from_subject_and_component_list(
            subject=If,
            components=[
                ComponentMetadata(name='condition', typing_=Expression, required=True),
                ComponentMetadata(name='if_clause', typing_=Expression, required=True),
                ComponentMetadata(name='else_clause', typing_=Expression, required=True)
            ]),
        ExpressionModel.from_subject_and_component_list(
            subject=Let,
            components=[
                ComponentMetadata(name='mapping', typing_=VariableMapping, init=dict, required=True),
                ComponentMetadata(name='body', typing_=Expression, required=True),
                # ComponentMetadata(name='closed', typing_=VariableMapping, init=dict)
            ]),
    ]
}

aa, bb = (Variable(name) for name in 'ab')
Or_ = Lambda((aa, bb), If(aa, True, bb), name='Or_')
del aa, bb
Nand = FunctionToken(name='Nand', variables=(Variable('a'), Variable('b')))
python_function = {Nand: lambda a, b: not (a and b)}
usable = {Nand, True, False, Variable, Lambda}
targets = [Or_]


def evaluate(expr: Expression,
             variable_mapping: Intersection[Mapping[Variable, Expression], frozendict] = frozendict()):
    if isinstance(expr, Beta):
        evaluated_head = evaluate(expr.head, variable_mapping)
        evaluated_args = (evaluate(x, variable_mapping) for x in expr.args)
        evaluated_kwargs = {k: evaluate(x, variable_mapping) for k, x in expr.kwargs.items()}
        if isinstance(evaluated_head, Lambda):
            ll = evaluated_head
            child_mapping = variable_mapping.update(chain(
                ll.closed.items(),
                zip(ll.variables, evaluated_args),
                evaluated_kwargs.items(),
            ))  # type: Intersection[Mapping[Variable, Expression], frozendict]
            # TODO: make sure have enough values, or use currying
            return evaluate(ll.body, variable_mapping=child_mapping)
        elif isinstance(evaluated_head, FunctionToken):
            return python_function[evaluated_head](*evaluated_args, **{k.name: v for k, v in evaluated_kwargs.items()})
        else:
            raise TypeError("{} has invalid type for Beta head".format(evaluated_head))
    elif isinstance(expr, Lambda):
        child_closed = variable_mapping.update(expr.closed)
        out = Lambda(expr.variables, expr.body, closed=child_closed, name=expr.name)
        return out
    elif isinstance(expr, If):
        if evaluate(expr.condition, variable_mapping):
            return evaluate(expr.if_clause, variable_mapping)
        else:
            return evaluate(expr.else_clause, variable_mapping)
    elif isinstance(expr, Variable):
        return variable_mapping[expr]
    elif isinstance(expr, Let):
        variables, values = map(tuple, zip(*expr.mapping.items()))
        child_mapping = variable_mapping.update(expr.mapping)
        # NOTE: need to pass child_mapping so that when values are evaluated, they get the Let mapping.
        # This makes recursion possible. If one of the values is a Lambda, it closes over the Let mapping.
        # Also note that the Lambda that the Let expands to does not actually need to close over `variable_mapping`
        # since it is immediately evaluated with those variables in scope.
        let_lambda = Lambda(variables, expr.body, closed=variable_mapping, name='let')
        # if expr.recur:
        #    child_mapping[expr.recur] = let_lambda  # enables recursive let
        return evaluate(Beta(let_lambda, values), child_mapping)
    else:
        return expr


def validate_solution(expr: Expression, usable_types, usable_values) -> typing.Tuple[bool, typing.Optional[Expression]]:
    def subs(_expr) -> typing.Iterable[Expression]:
        if isinstance(_expr, Beta):
            yield _expr.head
            yield from _expr.args
            yield from _expr.kwargs.values()
        elif isinstance(_expr, Lambda):
            yield _expr.body
        elif isinstance(_expr, If):
            yield from (_expr.condition, _expr.if_clause, _expr.else_clause)
        elif isinstance(_expr, Let):
            yield from _expr.mapping.values()
            yield _expr.body
        else:
            return

    try:
        if expr in usable_values:
            return True, None
    except TypeError:  # catch hash error
        pass

    ok_type = type(expr) in usable_types

    if not ok_type:
        return False, expr
    else:
        for sub in subs(expr):
            ok, witness = validate_solution(sub, usable_types, usable_values)
            if not ok:
                return ok, witness
        else:
            return True, None
