import os
import sys
# Fetch the best cache implementation we can
if sys.version_info[0] == 3:
    if sys.version_info[1] >= 9:
        from functools import cache
    else:
        from functools import lru_cache
        cache = lru_cache(None)

from elasticsearch.exceptions import NotFoundError
from os2phonebook.datastore import DataStore
from os2phonebook.helpers import log_factory
from os2phonebook.exceptions import InvalidRequestBody, InvalidSearchType, InvalidCredentials, InsufficientCredentials
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import NotFound
from flask import (
    Response,
    Blueprint,
    jsonify,
    current_app,
    request,
    render_template,
)

# Init logging
log = log_factory()

# Controller blueprint
api = Blueprint("routes", __name__)


@api.route("/", methods=["GET"])
@api.route("/api/status", methods=["GET"])
def show_status() -> Response:
    """Status endpoint shows application status and metadata.

    Returns:
        :obj:`Response`: Response with json body.

    """

    version = current_app.os2phonebook_version
    organisation_name = current_app.organisation_name

    status_response = {
        "app": "OS2Phonebook",
        "version": version,
        "organisation": organisation_name,
    }

    return jsonify(status_response)


@api.route("/api/org_units", methods=["GET"])
def all_org_units() -> Response:
    """Return a list of all organisation units.

    TODO:
        This endpoind should accept parameters
        to limit the amount of results.

    Example:

        The response body is formatted as follows:

        {
            "request_id": "c2667d614c954f9599615129e4029060",
            "results": [
                {
                    "name": "Kolding Kommune",
                    "parent": null,
                    "uuid": "f06ee470-9f17-566f-acbe-e938112d46d9"
                },
                {
                    "name": "Skole og Børn",
                    "parent": "f06ee470-9f17-566f-acbe-e938112d46d9",
                    "uuid": "7a8e45f7-4de0-44c8-990f-43c0565ee505"
                }
            ]
        }

    Returns:
        :obj:`Response`: Response with json body.

    """

    db = DataStore(current_app.connection)

    results = db.get_all_org_units()

    # There should be at least 1 org unit
    # For now just create a warning in the logs
    # Perhaps this should raise a `bad` type of exception instead
    if not results:
        log.warning(f"NO_RESULTS_ALL_ORG_UNITS")

    return jsonify(results)


@api.route("/api/org_unit/<uuid:uuid>", methods=["GET"])
def show_org_unit(uuid) -> Response:
    """Show org unit by uuid.

    Args:
        uuid (str): Org unit identifier <uuid>

    Returns:
        :obj:`Response`: Response with json body.

    """

    db = DataStore(current_app.connection)

    results = db.get_org_unit(
        uuid=uuid
    )

    return jsonify(results)


@api.route("/api/employee/<uuid:uuid>", methods=["GET"])
def show_employee(uuid) -> Response:
    """Show employee by uuid.

    Args:
        uuid (str): Employee identifier <uuid>

    Returns:
        :obj:`Response`: Response with json body.

    """

    db = DataStore(current_app.connection)

    # Retrieve employee by uuid
    results = db.get_employee(
        uuid=uuid
    )

    return jsonify(results)


@api.route("/api/search", methods=["GET"])
def show_search_schema():
    """Show post data schema for performing searches.

    Any search must be submit as a POST request
    and carry a json body with the following key value pairs,

        search_type: <string>
        search_value: <string>

    Example:
        {
            "search_type": "employee_by_email",
            "search_value": "someuser@example.org"
        }

    Returns:
        :obj:`Response`: Response with json body.

    """

    search_schema = {
        "method": "POST",
        "format": "json",
        "schema": {
            "search_type": {
                "type": "string",
                "required": True
            },
            "search_value": {
                "type": "string",
                "required": True
            }
        }
    }

    return jsonify(search_schema)


@api.route("/api/search", methods=["POST"])
def call_search_method():
    """Perform a high level search.

    Available search types:
        * employee_by_name
        * employee_by_phone
        * employee_by_email
        * employee_by_engagement
        * org_unit_by_name

    Returns:
        :obj:`Response`: Response with json body.

    """

    if not request.data:
        raise InvalidRequestBody("Request body (json) is missing")

    data = request.get_json()

    if "search_value" not in data:
        raise InvalidRequestBody(
            "Search value is missing from the request body"
        )

    if "search_type" not in data:
        raise InvalidRequestBody(
            "Search type is missing from the request body"
        )

    search_type = data["search_type"]
    search_value = data["search_value"]

    db = DataStore(current_app.connection)

    results = db.search(
        search_type=search_type,
        search_value=search_value,
        fuzzy_search=False
    )

    if not results:
        log.debug(
            f"NO_SEARCH_RESULTS search_type={search_type} search_value={search_value} # 1"
        )

        results = db.search(
            search_type=search_type,
            search_value=search_value,
            fuzzy_search=True
        )

    if not results:
        log.debug(
            f"NO_SEARCH_RESULTS search_type={search_type} search_value={search_value} # 2"
        )

    return jsonify(results)


#############
# DATA LOAD #
#############
auth = HTTPBasicAuth()

@auth.error_handler
def auth_error(status):
    if status == 401:
        raise InvalidCredentials()
    elif status == 403:
        raise InsufficientCredentials()


@cache
def gen_user_map():
    username = os.environ.get("OS2PHONEBOOK_DATALOADER_USERNAME", "dataloader")
    password = os.environ.get("OS2PHONEBOOK_DATALOADER_PASSWORD")
    # No password, no access
    if password is None:
        log.warning("No HTTP Basic Auth credentials configured thus dataload is disabled")
        return []
    return {
        username: generate_password_hash(password)
    }

@auth.verify_password
def verify_password(username, password):
    user_map = gen_user_map()
    # Only valid users can get their password checked
    if username in user_map:
        # Only if password matches, a login is successful
        if check_password_hash(user_map.get(username), password):
            return username
    return None

@api.route("/api/load-employees", methods=["POST"])
@auth.login_required
def load_employees():
    if not request.data:
        raise InvalidRequestBody("Request body (json) is missing")

    log.info("load_employees called")

    employees = request.get_json()

    # Connect to datastore
    db = DataStore(current_app.connection)
    db.delete_index("employees")

    for uuid, employee in employees.items():
        response = db.insert_index(
            index="employees", identifier=uuid, data=employee
        )
        log.debug(response)

    return jsonify({"data": len(employees)})

@api.route("/api/load-org-units", methods=["POST"])
@auth.login_required
def load_org_units():
    if not request.data:
        raise InvalidRequestBody("Request body (json) is missing")

    log.info("load_org_units called")

    org_units = request.get_json()

    # Connect to datastore
    db = DataStore(current_app.connection)
    db.delete_index("org_units")

    for uuid, unit in org_units.items():
        response = db.insert_index(
            index="org_units", identifier=uuid, data=unit
        )
        log.debug(response)

    return jsonify({"data": len(org_units)})


#####################################################################
#   ERROR HANDLING SECTION                                          #
#####################################################################

@api.app_errorhandler(NotFound)
@api.app_errorhandler(NotFoundError)
@api.app_errorhandler(InvalidSearchType)
@api.app_errorhandler(InvalidRequestBody)
@api.app_errorhandler(InvalidRequestBody)
@api.app_errorhandler(InvalidCredentials)
@api.app_errorhandler(InsufficientCredentials)
def invalid_validation_handler(error) -> Response:
    """Error handler for all common types

    The supported error types are as follows:
        * NotFound
        * NotFoundError
        * InvalidSearchType
        * InvalidRequestBody

    All error types above carry a `status_code`.
    
    NotFoundError is thrown when no record can be found
    by identifier, as such this will return status 404. 

    Args:
        error (Exception): An exception type error object

    Returns:
        :obj:`Response`: Response with error description.

    """

    status_code = 400

    if hasattr(error, "status_code"):
        status_code = error.status_code

    elif hasattr(error, "code"):
        status_code = error.code

    response = {
        "error": {
            "type": error.__class__.__name__,
            "message": str(error)
        }
    }

    log.warning("REQUEST_FAILED - {error}")

    return jsonify(response), status_code


@api.app_errorhandler(Exception)
def all_exception_handler(error):
    """Catch all error handler for (almost) all unexpected things.

    This error handler returns almost the same error description
    as the `common` handler.

    The main difference is that we are writing out the error type
    and dumping the entire error object to the debug log.

    Returns:
        :obj:`Response`: Response with error description.

    """

    status_code = 500

    error_class = error.__class__.__name__

    response = {
        "error": {
            "type": error_class,
            "message": "Unknown error occured, please contact administrator"
        }
    }

    log.error("UNKNOWN_EXCEPTION - {error_class}={error}")
    log.debug(error)

    return jsonify(response), status_code