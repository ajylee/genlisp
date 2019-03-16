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

BaseType = typing.Union[bool]


class CompoundExpression(abc.ABC):
    pass


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


Nand = CompoundExpression()


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


aa, bb = (Variable(name) for name in 'ab')
Or_ = Lambda((aa, bb), If(aa, True, bb), name='Or_')
del aa, bb
python_function = {Nand: lambda x, y: not (x and y)}
usable = {Nand, bool, Variable, Lambda}
targets = [Or_]


def evaluate(expr: Expression, variable_mapping: dict = {}):
    if isinstance(expr, Beta):
        evaluated_head = evaluate(expr.head, variable_mapping)
        evaluated_args = (evaluate(x, variable_mapping) for x in expr.args)
        evaluated_kwargs = {k: evaluate(x, variable_mapping) for k, x in expr.kwargs.items()}
        if isinstance(evaluated_head, Lambda):
            ll = evaluated_head
            child_mapping = {}
            child_mapping.update(variable_mapping)
            child_mapping.update(ll.closed)
            child_mapping.update(zip(ll.variables, evaluated_args))
            child_mapping.update(evaluated_kwargs)
            # TODO: make sure have enough values, or use currying
            return evaluate(ll.body, variable_mapping=child_mapping)
        else:
            return python_function[expr.head](*evaluated_args, **{k.name: v for k,v in evaluated_kwargs.items()})
    elif isinstance(expr, Lambda):
        child_closed = {}
        child_closed.update(variable_mapping)
        child_closed.update(expr.closed)
        out = Lambda(expr.variables, expr.body, child_closed, expr.name)
        return out
    elif isinstance(expr, If):
        if evaluate(expr.condition, variable_mapping):
            return evaluate(expr.if_clause, variable_mapping)
        else:
            return evaluate(expr.else_clause, variable_mapping)
    elif isinstance(expr, Variable):
        value = variable_mapping[expr]
        if isinstance(value, Lambda):
            return evaluate(value, variable_mapping)  # ensures closing over
        else:
            return value
    else:
        return expr


def validate_solution(expr: Expression):
    return ((type(expr) in usable)
            and ((not type(expr) in python_function) or all(validate_solution(sub) for sub in expr)))


def let(mapping, body):
    variables, values = map(tuple, zip(*mapping))
    return Beta(Lambda(variables, body, name='let'), values)
