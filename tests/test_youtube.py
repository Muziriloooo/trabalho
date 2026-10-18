import pytest


def test_youtube_example_is_available_without_creating_ip_camera(client, login):
    login()
    response = client.get('/monitoring')
    assert response.status_code == 200
    assert 'data-youtube-id="CKpA7U_wAbw"' in response.text
    assert 'Transmissão pública do YouTube' in response.text
    assert 'separado do inventário de câmeras IP' in response.text
    assert 'https://www.youtube.com/watch?v=CKpA7U_wAbw' in response.text
    assert '<iframe' not in response.text  # Conexão externa só depois do clique.
    assert 'src="https://www.youtube' not in response.text
    assert 'frame-src https://www.youtube-nocookie.com' in response.headers['Content-Security-Policy']


def test_frame_policy_stays_restricted_on_other_pages(client, login):
    assert "frame-src 'none'" in client.get('/login').headers['Content-Security-Policy']
    login()
    assert "frame-src 'none'" in client.get('/').headers['Content-Security-Policy']


def test_youtube_status_requires_console_session(client, login):
    assert client.get('/monitoring/youtube/status').status_code == 302
    login()
    response = client.get('/monitoring/youtube/status')
    assert response.json == {'status': 'public', 'video_id': 'CKpA7U_wAbw'}
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('email', ['physical@example.test', 'platform@example.test'])
def test_youtube_does_not_bypass_console_roles(client, login, email):
    login(email)
    assert client.get('/monitoring/youtube/status').status_code == 403
    assert client.get('/monitoring').status_code == 403
