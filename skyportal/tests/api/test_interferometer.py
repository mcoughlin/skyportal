import uuid

from skyportal.tests import api


def test_token_user_post_get_interferometer(super_admin_token):
    name = str(uuid.uuid4())
    post_data = {
        'name': name,
        'nickname': name,
        'lat': 0.0,
        'lon': 0.0,
    }

    status, data = api(
        'POST', 'interferometer', data=post_data, token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'

    interferometer_id = data['data']['id']
    status, data = api(
        'GET', f'interferometer/{interferometer_id}', token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'
    for key in post_data:
        assert data['data'][key] == post_data[key]


def test_fetch_interferometer_by_name(super_admin_token):
    name = str(uuid.uuid4())
    post_data = {
        'name': name,
        'nickname': name,
        'lat': 0.0,
        'lon': 0.0,
    }

    status, data = api(
        'POST', 'interferometer', data=post_data, token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'

    status, data = api('GET', f'interferometer?name={name}', token=super_admin_token)
    assert status == 200
    assert data['status'] == 'success'
    assert len(data['data']) == 1
    for key in post_data:
        assert data['data'][0][key] == post_data[key]


def test_token_user_update_interferometer(super_admin_token):
    name = str(uuid.uuid4())
    status, data = api(
        'POST',
        'interferometer',
        data={
            'name': name,
            'nickname': name,
            'lat': 0.0,
            'lon': 0.0,
        },
        token=super_admin_token,
    )
    assert status == 200
    assert data['status'] == 'success'

    interferometer_id = data['data']['id']
    status, data = api(
        'GET', f'interferometer/{interferometer_id}', token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'
    assert data['data']['lon'] == 0.0

    status, data = api(
        'PUT',
        f'interferometer/{interferometer_id}',
        data={
            'name': name,
            'nickname': name,
            'lat': 0.0,
            'lon': 20.0,
        },
        token=super_admin_token,
    )
    assert status == 200
    assert data['status'] == 'success'

    status, data = api(
        'GET', f'interferometer/{interferometer_id}', token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'
    assert data['data']['lon'] == 20.0


def test_token_user_delete_interferometer(super_admin_token):
    name = str(uuid.uuid4())
    status, data = api(
        'POST',
        'interferometer',
        data={
            'name': name,
            'nickname': name,
            'lat': 0.0,
            'lon': 0.0,
        },
        token=super_admin_token,
    )
    assert status == 200
    assert data['status'] == 'success'

    interferometer_id = data['data']['id']
    status, data = api(
        'GET', f'interferometer/{interferometer_id}', token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'

    status, data = api(
        'DELETE', f'interferometer/{interferometer_id}', token=super_admin_token
    )
    assert status == 200
    assert data['status'] == 'success'

    status, data = api(
        'GET', f'interferometer/{interferometer_id}', token=super_admin_token
    )
    assert status == 400