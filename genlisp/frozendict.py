"""
This could be optimized by storing an internal `types.MappingProxyType` and
granting access to it. However, this implementation of frozendict will probably only
ever be used if immutable.Map is unavailable.
"""

from typing import Mapping, Hashable, NamedTuple, Any
from itertools import chain
from cytoolz import merge

from types import MappingProxyType


class _frozendict(Mapping, Hashable):
    """Set tuples_memo if you want to memoize it"""
    tuples_memo = None

    def __init__(self, mapping_like=(), **kwargs):
        self._dict = self.proxy = MappingProxyType(merge(dict(mapping_like), kwargs))
        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.tuples())
        return self._hash

    def __getitem__(self, key):
        return self._dict.__getitem__(key)

    def __iter__(self):
        return self._dict.__iter__()

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return 'frozendict(' + repr(self._dict) + ')'

    def tuples(self):
        if self.tuples_memo is None:
            return frozenset(self._dict.items())
        else:
            return self.tuples_memo

    def items(self):
        return self._dict.items()

    def values(self):
        return self._dict.values()

    def keys(self):
        return self._dict.keys()

    def update(self, mapping_like, **kwargs):
        try:
            items = mapping_like.items()
        except AttributeError:
            items = mapping_like

        return __class__(chain(self.items(), items))


# for benchmarking
def hash_1(dd):
    # is actually faster than hash_2 but wastes space
    return hash(frozenset(dd.items()))


# for benchmarking
def hash_2(dd):
    hh = 0
    for tt in dd.items():
        hh ^= hash(tt)
    return hh

try:
    from immutables import Map as frozendict
except ImportError:
    frozendict = _frozendict
