from app import app


def test_index():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200


def test_divide_normal():
    client = app.test_client()
    resp = client.get("/divide/10/2")
    assert resp.status_code == 200
    assert resp.get_json()["result"] == 5.0


def test_divide_by_zero_returns_400_not_500():
    # This fails against the current app.py, which lets ZeroDivisionError
    # propagate into a 500. Overseer's Fixer agent should add a guard that
    # returns a 400 with an error message instead.
    client = app.test_client()
    resp = client.get("/divide/10/0")
    assert resp.status_code == 400
