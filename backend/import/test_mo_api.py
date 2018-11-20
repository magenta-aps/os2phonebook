import json

import mo_api
import do_import


def my_mo_get(url):
    url_file = '.test_data/mo/' + url.replace('/', '#') + '.json'
    with open(url_file, 'r') as f:
        return json.load(f)


def test_mo_data():
    """Test the two classes derived from MOData."""
    employee_uuid = '0014209a-8832-44b3-b7a0-4cc209a71993'
    ou_uuid = '0418617c-242f-4d9a-81cc-abb269ad27b4'

    ou = mo_api.MOOrgUnit(ou_uuid)
    ou.get = my_mo_get
    e = mo_api.MOEmployee(employee_uuid)
    e.get = my_mo_get

    # Test json function
    assert ou.json['name'] == 'Østervrå børnehus'
    assert e.json['name'] == 'Henry Olesen Steno Ahmad'


def test_get_employee_data():
    """Test the get_employee_data function in the do_import module."""
    employee_uuid = '0014209a-8832-44b3-b7a0-4cc209a71993'
    e = mo_api.MOEmployee(employee_uuid)
    e.get = my_mo_get
    e_data = do_import.get_employee_data(e)
    # Normalize
    e_data = json.loads(json.dumps(e_data))
    with open('.test_data/output/' + employee_uuid + '.json', 'r') as f:
        target_e_data = json.load(f)
        assert e_data == target_e_data


def test_get_orgunit_data():
    """Test the get_orgunit_data function in the do_import module."""
    orgunit_uuid = '0418617c-242f-4d9a-81cc-abb269ad27b4'
    ou = mo_api.MOOrgUnit(orgunit_uuid)
    ou.get = my_mo_get
    ou_data = do_import.get_orgunit_data(ou)
    # Normalize
    ou_data = json.loads(json.dumps(ou_data))
    with open('.test_data/output/' + orgunit_uuid + '.json', 'r') as f:
        target_ou_data = json.load(f)
        assert ou_data == target_ou_data
