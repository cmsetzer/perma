from warcio.timeutils import datetime_to_http_date

from django.urls import reverse

import pytest
from waffle.testutils import override_flag

#
#  Helpers
#

def get_playback(client, guid, follow=False, expect_iframe=True):
    url = reverse('single_permalink', kwargs={'guid': guid})
    response = client.get(url, secure=True, follow=follow)
    assert response.status_code != 500
    if expect_iframe:
        assert b"<iframe " in response.content
    return response


def check_memento_headers(link, response):
    assert response.headers['memento-datetime'] == datetime_to_http_date(link.creation_timestamp)
    assert f'<{link.submitted_url}>; rel=original,' in response.headers['link']
    assert f'<https://testserver/timegate/{link.submitted_url}>; rel=timegate,' in response.headers['link']
    assert f'<https://testserver/timemap/link/{link.submitted_url}>; rel=timemap; type=application/link-format,' in response.headers['link']
    assert f'<https://testserver/timemap/json/{link.submitted_url}>; rel=timemap; type=application/json,' in response.headers['link']
    assert f'<https://testserver/timemap/html/{link.submitted_url}>; rel=timemap; type=text/html,' in response.headers['link']
    assert f'<https://testserver/{link.guid}>; rel=memento; datetime="{datetime_to_http_date(link.creation_timestamp)}"' in response.headers['link']


#
# Tests
#

@pytest.mark.parametrize(
    "user",
    [
        None,
        "link_user",
        "org_user",
        "registrar_user",
        "admin_user"

    ]
)
def test_regular_archive(user, client, complete_link, request):
    link = complete_link

    if user:
        client.force_login(request.getfixturevalue(user))
    response = get_playback(client, link.guid)
    check_memento_headers(link, response)


@override_flag('wacz-playback', active=False)
def test_regular_archive_with_wacz_and_flag_off(client, complete_link_factory):
    link = complete_link_factory({"wacz_size": 1})

    response = get_playback(client, link.guid)
    # We are playing back a WARC
    assert b".warc.gz?" in response.content
    # We are not playing back a WACZ
    assert b".wacz?" not in response.content


@override_flag('wacz-playback', active=True)
def test_regular_archive_with_wacz_and_flag_on(client, complete_link_factory):
    link = complete_link_factory({"wacz_size": 1})

    response = get_playback(client, link.guid)
    # We are not playing back a WARC
    assert b".warc.gz?" not in response.content
    # We are playing back a WACZ
    assert b".wacz?" in response.content


@override_flag('wacz-playback', active=True)
def test_regular_archive_without_wacz_and_flag_on(client, complete_link_factory):
    link = complete_link_factory({"wacz_size": 0})

    response = get_playback(client, link.guid)
    # We are playing back a WARC
    assert b".warc.gz?" in response.content
    # We are not playing back a WACZ
    assert b".wacz?" not in response.content


@pytest.mark.parametrize(
    "user",
    [
        None,
        "link_user",
        "org_user",
        "registrar_user",
        "admin_user"

    ]
)
def test_archive_without_capture_job(user, client, complete_link_without_capture_job, request):
    link = complete_link_without_capture_job

    if user:
        client.force_login(request.getfixturevalue(user))
    response = get_playback(client, link.guid)
    check_memento_headers(link, response)


@pytest.mark.parametrize(
    "job",
    [
        "pending_capture_job",
        "in_progress_capture_job",
        "failed_capture_job",
        "deleted_capture_job"

    ]
)
def test_archive_with_unsuccessful_capturejob(job, client, request):
    capture_job = request.getfixturevalue(job)
    get_playback(client, capture_job.link.guid)


def test_screenshot_only_archive_default_to_screenshot_view_false(client, complete_link_factory):
    """
    When there is just a screenshot, no primary capture, and "default to screenshot" is false,
    we should redirect to the image playback
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": False},
        primary_capture=False,
        screenshot_capture=True
    )
    response = get_playback(client, link.guid, follow=True)
    assert b'Enhance screenshot playback' in response.content
    assert response.request.get('QUERY_STRING') == 'type=image'


def test_capture_only_archive_default_to_screenshot_view_true(client, complete_link_factory):
    """
    When there is just a primary capture, no screenshot, and "default to screenshot" is true,
    we should redirect to the standard playback
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": True},
        primary_capture=True,
        screenshot_capture=False
    )
    response = get_playback(client, link.guid, follow=True)
    assert b'Enhance screenshot playback' not in response.content
    assert response.request.get('QUERY_STRING') == 'type=standard'


def test_screenshot_only_archive_default_to_screenshot_view_true(client, complete_link_factory):
    """
    When there is just a screenshot, no primary capture, and "default to screenshot" is true,
    there should not be a redirect the "type=image" query
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": True},
        primary_capture=False,
        screenshot_capture=True
    )
    response = get_playback(client, link.guid, follow=True)
    assert b'Enhance screenshot playback' in response.content
    assert response.request.get('QUERY_STRING') == ''


def test_capture_only_archive_default_to_screenshot_view_false(client, complete_link_factory):
    """
    When there is just a primary capture, no screenshot, "default to screenshot" is false,
    there should not be a redirect to the "type=standard" query
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": False},
        primary_capture=True,
        screenshot_capture=False
    )
    response = get_playback(client, link.guid, follow=True)
    assert response.request.get('QUERY_STRING') == ''


def test_full_archive_default_to_screenshot_view_false(client, complete_link_factory):
    """
    When there is BOTH a primary capture and a screenshot, and "default to screenshot" is false,
    there should not be a redirect to the "type=standard" query
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": False},
        primary_capture=True,
        screenshot_capture=True
    )
    response = get_playback(client, link.guid, follow=True)
    assert b'Enhance screenshot playback' not in response.content
    assert response.request.get('QUERY_STRING') == ''


def test_full_archive_default_to_screenshot_view_true(client, complete_link_factory):
    """
    When there is BOTH a primary capture and a screenshot and "default to screenshot" is true,
    there should not be a redirect to the "type=standard" query
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": True},
        primary_capture=True,
        screenshot_capture=True
    )
    response = get_playback(client, link.guid, follow=True)
    assert b'Enhance screenshot playback' in response.content
    assert response.request.get('QUERY_STRING') == ''


def test_capture_only_default_to_screenshot_view_true(client, complete_link_factory):
    """
    When there is just a primary capture, no screenshot, "default to screenshot" is true,
    we should redirect to the "type=standard" query
    """
    link = complete_link_factory(
        {"default_to_screenshot_view": True},
        primary_capture=True,
        screenshot_capture=False
    )
    response = get_playback(client, link.guid, follow=True)
    assert b'Enhance screenshot playback' not in response.content
    assert response.request.get('QUERY_STRING') == 'type=standard'


@pytest.mark.parametrize(
    "user",
    [
        None,
        "link_user",
        "org_user",
        "registrar_user",
        "admin_user"

    ]
)
def test_dark_archive(user, client, complete_link_factory, request):
    link = complete_link_factory({"is_private": True})

    if user:
        user = request.getfixturevalue(user)
        client.force_login(user)

    response = get_playback(client, link.guid)

    assert b"This record is private" in response.content
    assert 'memento-datetime' not in response.headers
    assert 'link' not in response.headers

    if user and user.is_staff:
        assert response.status_code == 200
    else:
        assert response.status_code == 403


# Feature temporarily disabled
# NB: this test has not been ported to Pytest syntax
"""
def test_redirect_to_download(self):
    with patch('perma.storage_backends.S3MediaStorage.open', lambda path, mode: open(os.path.join(settings.PROJECT_ROOT, 'perma/tests/assets/new_style_archive/archive.warc.gz'), 'rb')):
        # Give user option to download to view pdf if on mobile
        link = Link.objects.get(pk='7CF8-SS4G')

        client = Client(HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 6_1_4 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10B350 Safari/8536.25')
        response = client.get(reverse('single_permalink', kwargs={'guid': link.guid}), secure=True)
        self.assertIn(b"Perma.cc can\xe2\x80\x99t display this file type on mobile", response.content)

        # If not on mobile, display link as normal
        client = Client(HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/601.7.7 (KHTML, like Gecko) Version/9.1.2 Safari/601.7.7')
        response = client.get(reverse('single_permalink', kwargs={'guid': link.guid}), secure=True)
        self.assertNotIn(b"Perma.cc can\xe2\x80\x99t display this file type on mobile", response.content)
"""


def test_deleted(client, deleted_link):
    link = deleted_link
    response = get_playback(client, link.guid)
    assert response.status_code == 410
    assert b"This record has been deleted." in response.content
    assert 'memento-datetime' not in response.headers
    assert 'link' not in response.headers


@pytest.mark.parametrize(
    "guid",
    [
        'JJ99--JJJJ',
        '988-JJJJ=JJJJ',
    ]
)
@pytest.mark.django_db
def test_misformatted_nonexistent_links_404(guid, client):
    response = get_playback(client, guid, expect_iframe=False)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "guid",
    [
        'JJ99-JJJJ',
        '0J6pkzDeQwT',
    ]
)
@pytest.mark.django_db
def test_properly_formatted_nonexistent_links_404(guid, client):
    response = get_playback(client, guid, expect_iframe=False)
    assert response.status_code == 404


def test_non_canonical_format_redirects(client, link):
    response = get_playback(client, link.guid.lower(), expect_iframe=False)
    assert response.status_code == 301
    assert response.headers['location'] == f"/{link.guid}"


def test_replacement_link_redirects(client, link_factory):
    link = link_factory()
    to_replace = link_factory()

    link.replacement_link = to_replace
    link.save()

    response = get_playback(client, link.guid, expect_iframe=False)
    assert response.status_code == 302
    assert response.headers['location'] == reverse('single_permalink', kwargs={'guid': to_replace.guid})
