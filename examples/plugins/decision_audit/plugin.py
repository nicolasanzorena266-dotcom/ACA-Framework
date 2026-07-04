"""Reference Decision Audit plugin for the ACA Plugin SDK."""


def create_plugin(runtime_api=None):
    return {
        "name": "example.decision_audit",
        "capabilities": ("decision.audit",),
        "runtime_api_bound": runtime_api is not None,
    }


def on_activate(runtime_api=None):
    return {"active": True, "runtime_api_bound": runtime_api is not None}
