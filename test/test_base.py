from genlisp.base import *
import itertools


def test_evaluate():
    aa, bb = (Variable() for _ in range(2))
    ee = Beta(Or_, (aa, bb))
    vvs = frozendict({aa: True, bb: False})
    result = evaluate(ee, variable_mapping=vvs)
    assert result == vvs[aa] or vvs[bb]


def test_pyfunc():
    for aa, bb in itertools.product((True, False), repeat=2):
        res = evaluate(Beta(Nand, (aa, bb)))
        assert res == (not (aa and bb))


def test_lambda():
    for aa, bb in itertools.product((True, False), repeat=2):
        res = evaluate(Beta(Or_, (aa, bb)))
        assert res == (aa or bb)


def test_lambda_2():
    aa, bb = (Variable(name) for name in 'ab')
    ll = Lambda((aa, bb), Beta(Or_, (aa, bb)))
    beta = Beta(ll, (True, False))
    beta2 = Beta(ll, (), {aa: True, bb: False})
    assert evaluate(beta)
    assert evaluate(beta2)


def test_lambda_inside_lambda():
    aa, bb, cc = (Variable(name) for name in 'abc')

    ff = Lambda((aa, bb),
                Lambda((cc,),
                       Beta(Or_,
                            (Beta(Or_, (aa, cc)),
                             bb))))

    should_close_over = evaluate(Beta(ff, (True,), {bb: False}))
    assert aa in should_close_over.closed
    assert bb in should_close_over.closed

    for aa_value, bb_value, cc_value in itertools.product((True, False), repeat=3):
        assert evaluate(Beta(Beta(ff, (aa_value,), {bb: bb_value}),
                             (cc_value,))) == any([aa_value, bb_value, cc_value])


def test_shadowing():
    aa, bb, cc, ll = (Variable(name) for name in 'abcl')

    ff = Lambda((aa, bb, cc),
                Lambda((cc,),
                       Beta(Or_,
                            (Beta(Or_, (aa, cc)),
                             bb))))

    res = evaluate(Beta(Beta(ff, (False, False, False)),
                        (True,)))

    #print(res)
    assert res == any((False, False, True))


def test_recursive():
    aa, ll = (Variable(name) for name in 'al')

    bindings = {
        ll: Lambda((aa,),
                   If(aa, aa, Beta(ll, (Beta(Or_, (True, aa)),))),
                   name='recursive')
    }

    ee = Let(bindings, Beta(ll, (False,)))
    assert evaluate(ee)

    ee2 = Let(bindings, ll)
    assert ll in evaluate(ee2).closed
    assert evaluate(Beta(ee2, (False,)))

