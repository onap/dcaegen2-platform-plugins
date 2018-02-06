from dockerplugin import utils


def test_random_string():
    target_length = 10
    assert len(utils.random_string(target_length)) == target_length


def test_update_dict():
    d = { "a": 1, "b": 2 }
    u = { "a": 2, "b": 3 }
    assert utils.update_dict(d, u) == u
