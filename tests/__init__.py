"""CudyPy test suite."""
def response_raw(value):
    """Export model snapshots for assertions against synthetic wire fixtures."""
    if hasattr(value, "raw"):
        return value.raw
    if isinstance(value, (list, tuple)):
        return [response_raw(item) for item in value]
    return value
