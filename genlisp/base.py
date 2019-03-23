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

import typing
import abc
import attr
from uuid import uuid4, UUID
import cytoolz as tz


BaseType = typing.Union[bool]


class CompoundExpression(abc.ABC):
    pass


@attr.s(frozen=True, repr=False)
class Token(CompoundExpression):
    name: str = attr.ib(hash=True)

    def __repr__(self):
        return self.name


# Expression includes Lambda and Beta
Expression = typing.Union[BaseType, CompoundExpression]


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


Nand = Token(name='Nand')


@attr.s(auto_attribs=True)
class Lambda(CompoundExpression):
    variables: typing.Tuple[Variable, ...] = attr.ib()
    body: Expression = attr.ib()
    closed: typing.Mapping[Variable, Expression] = attr.Factory(dict)
    name: str = attr.ib(default=None)


@attr.s(auto_attribs=True)
class Beta(CompoundExpression):
    head: typing.Union[Expression] = attr.ib()  # must return callable type
    args: typing.Tuple[Expression, ...] = attr.ib()
    kwargs: typing.Mapping[Variable, Expression] = attr.ib(factory=dict)


@attr.s(auto_attribs=True)
class If(CompoundExpression):
    condition: Expression = attr.ib()
    if_clause: Expression = attr.ib()
    else_clause: Expression = attr.ib()


@attr.s(auto_attribs=True)
class Let(CompoundExpression):
    mapping: typing.Mapping[Variable, Expression] = attr.ib()
    body: Expression = attr.ib()
    closed: typing.Mapping[Variable, Expression] = attr.Factory(dict)
    recur: typing.Optional[Variable] = attr.ib(default=None)


aa, bb = (Variable(name) for name in 'ab')
Or_ = Lambda((aa, bb), If(aa, True, bb), name='Or_')
del aa, bb
python_function = {Nand: lambda x, y: not (x and y)}
usable = {Nand, bool, Variable, Lambda}
targets = [Or_]


def evaluate(expr: Expression, variable_mapping: typing.Mapping[Variable, Expression] = {}):
    if isinstance(expr, Beta):
        evaluated_head = evaluate(expr.head, variable_mapping)
        evaluated_args = (evaluate(x, variable_mapping) for x in expr.args)
        evaluated_kwargs = {k: evaluate(x, variable_mapping) for k, x in expr.kwargs.items()}
        if isinstance(evaluated_head, Lambda):
            ll = evaluated_head
            child_mapping = tz.merge(variable_mapping,
                                     ll.closed,
                                     dict(zip(ll.variables, evaluated_args)),
                                     evaluated_kwargs)  # type: typing.Dict[Variable, Expression]
            # TODO: make sure have enough values, or use currying
            return evaluate(ll.body, variable_mapping=child_mapping)
        else:
            return python_function[expr.head](*evaluated_args, **{k.name: v for k,v in evaluated_kwargs.items()})
    elif isinstance(expr, Lambda):
        child_closed = tz.merge(variable_mapping, expr.closed)
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
        child_mapping = tz.merge(variable_mapping, expr.mapping)
        # NOTE: need to pass child_mapping so that when values are evaluated, they get the Let mapping.
        # This makes recursion possible. If one of the values is a Lambda, it closes over the Let mapping.
        # Also note that the Lambda that the Let expands to does not actually need to close over `variable_mapping`
        # since it is immediately evaluated with those variables in scope.
        let_lambda = Lambda(variables, expr.body, closed=variable_mapping, name='let')
        if expr.recur:
            child_mapping[expr.recur] = let_lambda  # enables recursive let
        return evaluate(Beta(let_lambda, values), child_mapping)
    else:
        return expr


def validate_solution(expr: Expression, usable_types, usable_values) -> typing.Tuple[bool, typing.Optional[Expression]]:
    def subs(expr) -> typing.Iterable[Expression]:
        if isinstance(expr, Beta):
            yield expr.head
            yield from expr.args
            yield from expr.kwargs.values()
        elif isinstance(expr, Lambda):
            yield expr.body
        elif isinstance(expr, If):
            yield from (expr.condition, expr.if_clause, expr.else_clause)
        elif isinstance(expr, Let):
            yield from expr.mapping.values()
            yield expr.body
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
