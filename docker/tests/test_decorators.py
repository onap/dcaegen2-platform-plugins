from dockerplugin import decorators as dec


def test_wrapper_merge_inputs():
    properties = { "app_config": {"nested": { "a": 123, "b": 456 }, "foo": "duh"},
            "image": "some-docker-image" }
    kwargs = { "app_config": {"nested": {"a": 789, "c": "zyx"}} }

    def task_func(**inputs):
        return inputs

    expected = { "app_config": {"nested": { "a": 789, "b": 456, "c": "zyx" },
        "foo": "duh"}, "image": "some-docker-image" }

    assert expected == dec._wrapper_merge_inputs(task_func, properties, **kwargs)

