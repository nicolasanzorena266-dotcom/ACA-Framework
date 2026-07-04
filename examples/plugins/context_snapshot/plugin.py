"""Reference Context Snapshot plugin for the ACA Plugin SDK."""


def create_plugin(runtime_api=None):
    return {
        "name": "example.context_snapshot",
        "capabilities": ("context.snapshot",),
        "runtime_api_bound": runtime_api is not None,
    }


def on_initialize(runtime_api=None):
    return {"initialized": True, "runtime_api_bound": runtime_api is not None}
