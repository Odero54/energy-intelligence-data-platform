# Superset runtime config for local dev stack.
#
# Monkey-patch: Superset 3.1.3 stores user.id (int) as the JWT subject, but
# flask-jwt-extended 4.4+ requires sub to be a string (RFC 7519 §4.1.2).
# This patch coerces integer subs to strings on decode so the API works.
import flask_jwt_extended.utils as _fje

_orig_decode = _fje.decode_token


def _patched_decode(encoded_token, *args, **kwargs):
    data = _orig_decode(encoded_token, *args, **kwargs)
    if isinstance(data.get("sub"), int):
        data = {**data, "sub": str(data["sub"])}
    return data


_fje.decode_token = _patched_decode
