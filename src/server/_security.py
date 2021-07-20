from typing import Dict, List, Optional, Set, Union, cast
from enum import Enum
from datetime import date, timedelta
from functools import wraps
from os import environ
from flask import g
from werkzeug.local import LocalProxy
from sqlalchemy import Table, Column, String, Integer
from ._common import app, request, db
from ._exceptions import MissingAPIKeyException, UnAuthenticatedException
from ._db import metadata, TABLE_OPTIONS

API_KEY_REQUIRED_STARTING_AT = date.fromisoformat(environ.get('API_REQUIRED_STARTING_AT', '3000-01-01'))
API_KEY_HARD_WARNING = API_KEY_REQUIRED_STARTING_AT - timedelta(days=14)
API_KEY_SOFT_WARNING = API_KEY_HARD_WARNING - timedelta(days=14)

API_KEY_WARNING_TEXT = "an api key will be required starting at {}, go to https://delphi.cmu.edu to request one".format(API_KEY_REQUIRED_STARTING_AT)

user_table = Table(
    "api_user",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("api_key", String(50)),
    Column("email", String(255)),
    Column("roles", String(255)),
    **TABLE_OPTIONS,
)


class UserRole(str, Enum):
    afhsb = "afhsb"
    cdc = "cdc"
    fluview = "fluview"
    ght = "ght"
    norostat = "norostat"
    quidel = "quidel"
    sensors = "sensors"
    sensor_twtr = "sensor_twtr"
    sensor_gft = "sensor_gft"
    sensor_ght = "sensor_ght"
    sensor_ghtj = "sensor_ghtj"
    sensor_cdc = "sensor_cdc"
    sensor_quid = "sensor_quid"
    sensor_wiki = "sensor_wiki"
    twitter = "twitter"


# begin sensor query authentication configuration
#   A multimap of sensor names to the "granular" auth tokens that can be used to access them; excludes the "global" sensor auth key that works for all sensors:
GRANULAR_SENSOR_ROLES = {
    "twtr": UserRole.sensor_twtr,
    "gft": UserRole.sensor_gft,
    "ght": UserRole.sensor_ght,
    "ghtj": UserRole.sensor_ghtj,
    "cdc": UserRole.sensor_cdc,
    "quid": UserRole.sensor_quid,
    "wiki": UserRole.sensor_wiki,
}

#   A set of sensors that do not require an auth key to access:
OPEN_SENSORS = [
    "sar3",
    "epic",
    "arch",
]


class User:
    user_id: str
    roles: Set[UserRole]
    authenticated: bool

    def __init__(self, user_id: str, authenticated: bool, roles: Set[UserRole]) -> None:
        self.user_id = user_id
        self.authenticated = authenticated
        self.roles = roles

    def has_role(self, role: UserRole) -> bool:
        return role in self.roles


ANONYMOUS_USER = User("anonymous", False, set())


def _find_user(api_key: Optional[str]) -> User:
    if not api_key:
        return ANONYMOUS_USER
    stmt = user_table.select().where(user_table.c.api_key == api_key)
    user = db.execution_options(stream_results=False).execute(stmt).first()
    if user is None:
        return ANONYMOUS_USER
    else:
        return User(str(user.id), True, set(user.roles.split(",")))

def list_users() -> List[Dict[str, Union[int, str]]]:
    return [r for r in db.execution_options(stream_results=False).execute(user_table.select())]


def resolve_auth_token() -> Optional[str]:
    # auth request param
    if "auth" in request.values:
        return request.values["auth"]
    if "api_key" in request.values:
        return request.values["api_key"]
    # user name password
    if request.authorization and request.authorization.username == "epidata":
        return request.authorization.password
    # bearer token authentication
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    return None


def _get_current_user() -> User:
    if "user" not in g:
        api_key = resolve_auth_token()
        user = _find_user(api_key)
        if not user.authenticated and require_api_key():
            raise MissingAPIKeyException()
        g.user = user
    return g.user


current_user: User = cast(User, LocalProxy(_get_current_user))


def require_api_key() -> bool:
    n = date.today()
    return n >= API_KEY_REQUIRED_STARTING_AT


def show_soft_api_key_warning() -> bool:
    n = date.today()
    return not current_user.authenticated and n > API_KEY_SOFT_WARNING and n < API_KEY_HARD_WARNING


def show_hard_api_key_warning() -> bool:
    n = date.today()
    return not current_user.authenticated and n > API_KEY_HARD_WARNING


@app.before_request
def resolve_user():
    if request.path.startswith("/lib") or request.path.startswith('/admin'):
        return
    # try to get the db
    try:
        _get_current_user()
    except MissingAPIKeyException as e:
        raise e
    except UnAuthenticatedException as e:
        raise e
    except:
        app.logger.error("user connection error", exc_info=True)
        if require_api_key():
            raise MissingAPIKeyException()
        else:
            g.user = ANONYMOUS_USER


def require_role(required_role: Optional[UserRole]):
    def decorator_wrapper(f):
        if not required_role:
            return f

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user or not current_user.has_role(required_role):
                raise UnAuthenticatedException()
            return f(*args, **kwargs)

        return decorated_function

    return decorator_wrapper