from compuoti.pareto import dominates, pareto_filter


def test_dominance():
    assert dominates((10, 8), (9, 7))
    assert not dominates((10, 7), (9, 8))


def test_pareto_filter():
    points = [(10, 8), (9, 7), (8, 10)]
    assert pareto_filter(points) == [(10, 8), (8, 10)]
