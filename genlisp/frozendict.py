from typing import Mapping, Hashable, NamedTuple, Any
from collections.abc import ItemsView, ValuesView
from toolz import first


class Item(NamedTuple):
    key: Hashable
    value: Any
    #def __init__(self, key, value):
    #    self.key = key
    #    self.value = value

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        if type(other) is _FrozenDictLookupKey:
            return self.key.__eq__(other)
        else:
            return tuple.__eq__(self, other)


class _FrozenDictLookupKey:
    """Single purpose class"""

    def __init__(self, key):
        self._key = key

    def __hash__(self):
        return hash(self._key)

    def __cmp__(self, other):
        if type(other) is Item:
            return self._key.__cmp__(other.key)
        else:
            return super().__cmp__(other)

    def __eq__(self, other):
        """When equal and other is an Item, copy the value. This is the trick to frozendict."""
        if type(other) is Item:
            result = self._key.__eq__(other.key)
            if result:
                self.value = other.value
            return result
        else:
            return super().__eq__(other)


class frozendict(Mapping, Hashable):
    """Set tuples_memo if you want to memoize it"""
    tuples_memo = None

    def __init__(self, mapping_like=()):
        try:
            items = mapping_like.items()
        except AttributeError:
            items = mapping_like

        self._set = frozenset(
            Item(k, v) for k, v in items)

        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.tuples())
        return self._hash

    def __getitem__(self, key):
        try:
            return first(frozenset((_FrozenDictLookupKey(key),)).intersection(self._set)).value
        except StopIteration:
            raise KeyError(key)

    def __iter__(self):
        for item in iter(self._set):
            yield item.key

    def __len__(self):
        return len(self._set)

    def __repr__(self):
        return 'frozendict(' + repr(dict(self)) + ')'

    def tuples(self):
        if self.tuples_memo is None:
            return frozenset(map(tuple, self._set))
        else:
            return self.tuples_memo

    def items(self):
        return FrozenDictItemsView(self)


class FrozenDictItemsView(ItemsView):
    def __init__(self, fz: frozendict):
        self._set = fz._set
        self._mapping = fz

    def __contains__(self, item):
        return Item(*item) in self._set

    def __iter__(self):
        return map(tuple, self._set)


class FrozenDictValuesView(ValuesView):
    def __init__(self, fz: frozendict):
        self._set = fz._set
        self._mapping = fz

    def __iter__(self):
        for item in self._set:
            yield item.value
