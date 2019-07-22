import abc
import attr
from uuid import UUID, uuid4
from .base import Expression, Variable, VariableMapping, VariableTuple
from typing import Union, Set, List, Optional, Dict
from functools import reduce
from itertools import chain


@attr.s(cmp=True, hash=False)
class ExpressionPlan:
    head: type = attr.ib()
    parts: Dict[str, Union['ExpressionPlan', Expression,
                           VariableMapping.to_type_hint(),
                           VariableTuple.to_type_hint()]] = attr.ib(factory=dict)
    finished: bool = attr.ib(default=False)
    uuid: UUID = attr.ib(factory=uuid4)

    def __hash__(self):
        return hash(self.uuid)


@attr.s
class World:
    variables: Set[Variable]
    expressions: List[Expression]
    incomplete_expressions: Set[ExpressionPlan]


@attr.s
class ComponentReference:
    base: Union[Expression, ExpressionPlan] = attr.ib()
    attr_chain: List[str] = attr.ib()

    def set(self, value):
        penultimate = reduce(getattr, self.attr_chain[:-1], self.base)
        return setattr(penultimate, self.attr_chain[-1], value)

    def get(self):
        return reduce(getattr, self.attr_chain, self.base)
