from genlisp.frozendict import frozendict
import random

test_dicts = [{1: 2},
              {1: 3},
              {1: 2, 3: 4},
              dict(a=1, b=2, c=3, d=4, e=5),
              dict(a=3, b=1, c=3, d=4, e=5),
              {ii: random.randint(0, 10000) for ii in range(20000)},
              {ii: random.randint(0, 10000) for ii in range(20000)},
              ]


def test_get():
    for aa in test_dicts:
        bb = frozendict(aa)
        for kk in aa:
            assert aa[kk] == bb[kk]


def test_eq_and_hash():
    frozen = [frozendict(x) for x in test_dicts]

    for ii, aa in enumerate(test_dicts):  # type: (int, dict)
        bb = frozendict(aa)
        cc = frozendict(aa)
        assert bb == cc
        assert hash(bb) == hash(cc)
        for jj, bb_jj in enumerate(frozen):
            if ii != jj:
                assert bb != bb_jj
                assert hash(bb) != hash(bb_jj)

        assert aa == dict(bb)


def test_items():
    for aa in test_dicts:
        bb = frozendict(aa)
        for item in aa.items():
            assert item in bb.items()

        #print(set(aa.items()), set(bb.items()))
        assert set(aa.items()) == set(bb.items())


def test_values():
    for aa in test_dicts:
        bb = frozendict(aa)

        # loop would grow as O(n^2) if we didn't break early
        for cnt, vv in enumerate(aa.values()):
            if cnt > 100:
                break
            assert vv in bb.values()

        assert set(aa.values()) == set(bb.values())
