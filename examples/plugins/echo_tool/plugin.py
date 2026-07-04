"""Reference Echo Tool plugin for the ACA Plugin SDK.

The current Plugin SDK stages discover, validate, load and lifecycle-manage
plugin metadata only. This module exists as a stable future entrypoint target;
it must not be imported by the loader during Sprint 39.
"""

PLUGIN_STATE = {"activated": False}


def create_plugin(runtime_api=None):
    return {
        "name": "example.echo_tool",
        "capabilities": ("tool.echo",),
        "runtime_api_bound": runtime_api is not None,
    }


def on_activate(runtime_api=None):
    PLUGIN_STATE["activated"] = True
    return {"activated": True, "runtime_api_bound": runtime_api is not None}


def on_stop(runtime_api=None):
    PLUGIN_STATE["activated"] = False
    return {"activated": False, "runtime_api_bound": runtime_api is not None}
