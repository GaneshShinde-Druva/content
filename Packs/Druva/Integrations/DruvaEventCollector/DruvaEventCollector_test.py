from datetime import datetime

import demistomock as demisto
import pytest
import requests
from CommonServerPython import DemistoException
from DruvaEventCollector import (
    DATE_FORMAT_FOR_TOKEN,
    MAX_FETCH,
    Client,
    fetch_events,
    get_events,
    druva_get_all_events_command,
    add_time_to_events_v3,
)
from DruvaEventCollector import (
    test_module as run_test_module,
)
from freezegun import freeze_time

RESPONSE_WITH_EVENTS_1 = {
    "events": [
        {
            "eventID": 0,
            "eventType": "Backup",
            "profileName": "Default",
            "inSyncUserName": "user name",
            "clientVersion": "7.5.0r(23c42be5)",
            "clientOS": "Office 365 Exchange Online",
            "ip": "",
            "inSyncUserEmail": "test@test.com",
            "eventDetails": "",
            "timestamp": "2024-05-25T18:52:48Z",
            "inSyncUserID": 0,
            "profileID": 0,
            "initiator": None,
            "inSyncDataSourceID": 0,
            "eventState": "Backed up with Errors",
            "inSyncDataSourceName": "Exchange Online",
            "severity": 4,
            "facility": 23,
        }
    ],
    "nextPageExists": False,
    "tracker": "xxxx",
}
RESPONSE_WITH_EVENTS_2 = {
    "events": [
        {
            "eventID": 1,
            "eventType": "Backup",
            "profileName": "Default",
            "inSyncUserName": "user name",
            "clientVersion": "7.5.0r(23c42be5)",
            "clientOS": "Office 365 Exchange Online",
            "ip": "",
            "inSyncUserEmail": "test@test.com",
            "eventDetails": "",
            "timestamp": "2024-05-25T18:52:48Z",
            "inSyncUserID": 1,
            "profileID": 1,
            "initiator": None,
            "inSyncDataSourceID": 1,
            "eventState": "Backed up with Errors",
            "inSyncDataSourceName": "Exchange Online",
            "severity": 4,
            "facility": 23,
        }
    ],
    "nextPageExists": False,
    "tracker": "yyyy",
}
RESPONSE_WITHOUT_EVENTS = {"events": [], "nextPageExists": False, "tracker": "xxxx"}
INVALID_RESPONSE = {
    "events": [
        {
            "eventID": 0,
            "eventType": "Backup",
            "profileName": "Default",
            "inSyncUserName": "user name",
            "clientVersion": "7.5.0r(23c42be5)",
            "clientOS": "Office 365 Exchange Online",
            "ip": "",
            "inSyncUserEmail": "test@test.com",
            "eventDetails": "",
            "timestamp": "2024-05-25T18:52:48Z",
            "inSyncUserID": 0,
            "profileID": 0,
            "initiator": None,
            "inSyncDataSourceID": 0,
            "eventState": "Backed up with Errors",
            "inSyncDataSourceName": "Exchange Online",
            "severity": 4,
            "facility": 23,
        }
    ],
    "nextPageExists": False,
}


@pytest.fixture()
def mock_client(mocker) -> Client:
    mocker.patch.object(Client, "login", return_value="DUMMY_TOKEN")
    client = Client(
        base_url="test",
        client_id="client_id",
        secret_key="secret_key",
        max_fetch=MAX_FETCH,
        verify=False,
        proxy=False,
    )
    client._set_headers("DUMMY_TOKEN")
    return client


def test_test_module_command(mocker, mock_client):
    """
    Given:
    - test module command
    - an empty (yet valid) response from Druva

    When:
    - Pressing test button

    Then:
    - Test module passed
    """
    mocker.patch.object(
        mock_client,
        "search_events",
        return_value={"events": [], "tracker": "DUMMY_TRACKER"},
    )
    result = run_test_module(client=mock_client)
    assert result == "ok"


def test_test_module_command_failure(mocker, mock_client):
    """
    Given:
    - test module command

    When:
    - Pressing test button

    Then:
    - Test module failed
    """
    mocker.patch.object(
        mock_client,
        "_http_request",
        side_effect=DemistoException(message="Error: invalid_grant"),
    )
    with pytest.raises(DemistoException):
        run_test_module(client=mock_client)


def test_get_events_command(mocker, mock_client):
    """
    Given:
    - get_events command

    When:
    - running get events command

    Then:
    - events and tracker as expected
    """
    mocker.patch.object(mock_client, "search_events", return_value=RESPONSE_WITH_EVENTS_1)
    events, tracker = get_events(client=mock_client)

    assert tracker == "xxxx"
    assert len(events) == 1


def test_get_events_command_failure(mocker, mock_client):
    """
    Given:
    - a mocked client
    - mocked response: invalid response structure, since it does not have the 'tracker' key as expected

    When:
    - running get events command

    Then:
    - Ensure KeyError exception was thrown due to invalid response

    """
    mocker.patch.object(mock_client, "search_events", return_value=INVALID_RESPONSE)
    with pytest.raises(KeyError):
        get_events(client=mock_client)


def test_refresh_access_token(mocker, mock_client):
    """
    Given:
    - a mock client

    When:
    - running _refresh_access_token method

    Then:
    - Ensure exception is thrown
    - Ensure informative message was shown
    """
    response = requests.Response()
    response.status_code = 400

    mocker.patch.object(
        mock_client,
        "_http_request",
        side_effect=DemistoException(message="invalid_grant", res=response),
    )

    error_message = "Error in test-module: Make sure Server URL, Client ID and Secret Key are correctly entered."

    with pytest.raises(DemistoException, match=error_message):
        mock_client._refresh_access_token()


def test_search_events_called_with(mocker, mock_client):
    """
    Given:
    - a mock client

    When:
    - running search_events method

    Then:
    -  Ensure all arguments were sent to the api call as expected
    """

    http_mock = mocker.patch.object(mock_client, "_http_request", return_value=RESPONSE_WITHOUT_EVENTS)

    mock_client.search_events(tracker="xxxx")
    http_mock.assert_called_with(
        method="GET",
        url_suffix="/insync/eventmanagement/v2/events?tracker=xxxx",
        headers={"Authorization": "Bearer DUMMY_TOKEN", "accept": "application/json"},
    )


def test_search_events_failure(mocker, mock_client):
    """
    Given:
    - a mock client

    When:
    - running search_events method

    Then:
    -  Ensure an exception was thrown due to invalid tracker
    """

    mocker.patch.object(
        mock_client,
        "_http_request",
        side_effect=DemistoException(message="Error: Invalid tracker"),
    )
    with pytest.raises(DemistoException):
        mock_client.search_events(tracker="xxxx")


def test_fetch_events_command(mocker, mock_client):
    """
    Given:
    - fetch events command

    When:
    - Running fetch-events command

    Then:
    - Ensure number of events fetched, and the next run, match the response data
    """
    # First fetch
    mocker.patch.object(mock_client, "search_events", return_value=RESPONSE_WITH_EVENTS_1)
    first_run = {}
    events, tracker_for_second_run = fetch_events(client=mock_client, last_run=first_run, max_fetch=MAX_FETCH)

    assert len(events) == 1
    assert tracker_for_second_run["tracker"] == "xxxx"
    assert events[0]["eventID"] == 0

    # Second fetch
    mock_search_events = mocker.patch.object(mock_client, "search_events", return_value=RESPONSE_WITH_EVENTS_2)
    events, tracker_for_third_run = fetch_events(client=mock_client, last_run=tracker_for_second_run, max_fetch=MAX_FETCH)
    mock_search_events.assert_called_with(tracker_for_second_run.get("tracker"))
    assert len(events) == 1
    assert tracker_for_third_run["tracker"] == "yyyy"
    assert events[0]["eventID"] == 1


@freeze_time(datetime(2022, 2, 28, 11, 10))
@pytest.mark.parametrize(
    "integration_context",
    [
        ({}),
        (
            {
                "Token": "DUMMY TOKEN",
                "expiration_time": datetime(2022, 2, 28, 10, 50).strftime(DATE_FORMAT_FOR_TOKEN),
            }
        ),
    ],
)
def test_login_invalid_token(mocker, integration_context):
    """
    Given:
    - An IntegrationContext without a Token or one that has expired

    When:
    - Build a client (for checking login)

    Then:
    - Ensure a new token is generated
    """
    mocker.patch.object(demisto, "getIntegrationContext", return_value=integration_context)
    mocker.patch.object(demisto, "setIntegrationContext")
    mock_refresh_access_token = mocker.patch.object(Client, "_refresh_access_token", return_value=("", 0))
    Client(
        base_url="test",
        client_id="client_id",
        secret_key="secret_key",
        max_fetch=MAX_FETCH,
        verify=False,
        proxy=False,
    )
    mock_refresh_access_token.assert_called_once_with()


@freeze_time(datetime(2022, 2, 28, 11, 00))
def test_login_valid_token(mocker):
    """
    Given:
    - An IntegrationContext with valid Access Token

    When:
    - Build a client (for checking login)

    Then:
    - Ensure a new token is not generated
    """
    mocker.patch.object(
        demisto,
        "getIntegrationContext",
        return_value={
            "Token": "DUMMY TOKEN",
            "expiration_time": datetime(2022, 2, 28, 11, 10).strftime(DATE_FORMAT_FOR_TOKEN),
        },
    )
    mocker.patch.object(demisto, "setIntegrationContext")
    mock_refresh_access_token = mocker.patch.object(Client, "_refresh_access_token", return_value=("DUMMY_TOKEN", 1800))
    Client(
        base_url="test",
        client_id="client_id",
        secret_key="secret_key",
        max_fetch=MAX_FETCH,
        verify=False,
        proxy=False,
    )
    assert not mock_refresh_access_token.called


def test_max_fetch_validation():
    """
    Given:
    - invalid max_fetch (more than 10,000)

    When:
    - init the client

    Then:
    - DemistoException is thrown with an appropriate message
    """

    with pytest.raises(DemistoException, match=f"The maximum number of events per fetch should be between 1 - {MAX_FETCH}"):
        Client(
            base_url="test",
            client_id="client_id",
            secret_key="secret_key",
            max_fetch=(MAX_FETCH + 1),
            verify=False,
            proxy=False,
        )


def test_fetch_events_invalid_tracker(mocker, mock_client):
    """
    Given:
    - fetch events command

    When:
    - Running fetch-events command
    - Mocking the second fetch to throw an exception to Invalid tracker

    Then:
    - Ensure exception is caught
    - Ensure same tracker is returned (as we got at the previous call)
    - Ensure no events are returned
    """
    # First fetch
    mocker.patch.object(mock_client, "search_events", return_value=RESPONSE_WITH_EVENTS_1)
    events, tracker_for_second_run = fetch_events(client=mock_client, last_run={}, max_fetch=MAX_FETCH)

    # Second fetch
    mocker.patch.object(mock_client, "search_events", side_effect=Exception("Invalid tracker"))
    events, tracker_for_third_run = fetch_events(client=mock_client, last_run=tracker_for_second_run, max_fetch=MAX_FETCH)

    # same tracker should be returned when "Invalid tracker" exception is thrown and no events
    assert tracker_for_third_run["tracker"] == tracker_for_second_run["tracker"]
    assert events == []


# ======================== v3 API Tests ========================

# Mock response data for v3 API
V3_RESPONSE_WITH_EVENTS = {
    "events": [
        {
            "id": 840135132,
            "category": "EVENT",
            "details": {
                "location": "Pune,India",
                "adminName": "Test Admin",
                "alertName": "Admin Login Event - New Location",
                "adminEmail": "test@gmail.com",  # disable-secrets-detection
                "loginResult": "Success",
                "adminIPAddress": "223.123.76.33",  # disable-secrets-detection
                "adminLoginTime": "2025-10-31T07:01:58Z",
            },
            "feature": "Alerts And Notifications",
            "globalID": "e0663cd2-1ff2-46dc-86fe-80de3bccfe74-10608",
            "timeStamp": 1761894118,
            "productID": 4097,
            "syslogFacility": 1,
            "syslogSeverity": 4,
            "type": "Alert",
        },
        {
            "id": 840135133,
            "category": "ALERT",
            "details": {"resourceName": "test-resource", "state": "Success"},
            "feature": "Ransomware Recovery",
            "globalID": "e0663cd2-1ff2-46dc-86fe-80de3bccfe74-10608",
            "timeStamp": 1761894200,
            "productID": 4097,
            "syslogFacility": 1,
            "syslogSeverity": 3,
            "type": "Quarantine",
        },
    ],
    "nextPageToken": "eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ==",
}

V3_RESPONSE_WITHOUT_EVENTS = {"events": [], "nextPageToken": ""}
V3_RESPONSE_EMPTY_WITH_TOKEN = {"events": [], "nextPageToken": "eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ=="}


def test_get_all_events_command_with_filters(mocker, mock_client):
    """
    Given:
    - druva-get-all-events command with filters

    When:
    - running get-all-events command with product_id, category, and syslog_severity filters

    Then:
    - Ensure correct API method is called with proper parameters
    - Ensure events are returned correctly
    - Ensure nextPageToken is returned in context
    """
    mocker.patch.object(mock_client, "get_all_events", return_value=V3_RESPONSE_WITH_EVENTS)

    args = {"product_id": "4097", "category": "ALERT", "syslog_severity": "3", "page_size": "100", "should_push_events": "false"}

    result = druva_get_all_events_command(mock_client, args)

    # Verify the API was called with correct parameters
    mock_client.get_all_events.assert_called_once_with(
        product_id="4097",
        syslog_severity="3",
        category="ALERT",
        event_type=None,
        feature=None,
        page_token=None,
        page_size=100,
    )

    # Verify the output
    assert result.outputs is not None
    outputs = result.outputs
    assert outputs["totalEvents"] == 2  # type: ignore[index]
    assert outputs["hasMore"] is True  # type: ignore[index]
    assert outputs["nextPageToken"] == "eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ=="  # type: ignore[index]
    assert len(outputs["events"]) == 2  # type: ignore[index]


def test_get_all_events_command_no_events(mocker, mock_client):
    """
    Given:
    - druva-get-all-events command
    - API returns no events

    When:
    - running get-all-events command

    Then:
    - Ensure empty events list is returned
    - Ensure hasMore is False
    - Ensure readable output indicates no events found
    """
    mocker.patch.object(mock_client, "get_all_events", return_value=V3_RESPONSE_WITHOUT_EVENTS)

    args = {"product_id": "4097", "should_push_events": "false"}

    result = druva_get_all_events_command(mock_client, args)

    assert result.outputs is not None
    outputs = result.outputs
    assert outputs["totalEvents"] == 0  # type: ignore[index]
    assert outputs["hasMore"] is False  # type: ignore[index]
    assert outputs["nextPageToken"] == ""  # type: ignore[index]
    assert "No events found" in result.readable_output


def test_get_all_events_empty_with_token(mocker, mock_client):
    """
    Given:
    - druva-get-all-events command
    - API returns empty events array but includes nextPageToken (edge case)

    When:
    - running get-all-events command

    Then:
    - Ensure hasMore is False (empty array means last page)
    - Ensure nextPageToken is cleared (terminated)
    - Ensure pagination indicates no more events
    """
    mocker.patch.object(mock_client, "get_all_events", return_value=V3_RESPONSE_EMPTY_WITH_TOKEN)

    args = {"product_id": "4097", "should_push_events": "false"}

    result = druva_get_all_events_command(mock_client, args)

    assert result.outputs is not None
    outputs = result.outputs
    assert outputs["totalEvents"] == 0  # type: ignore[index]
    assert outputs["hasMore"] is False  # type: ignore[index]
    assert outputs["nextPageToken"] == ""  # type: ignore[index]
    assert "No more events available" in result.readable_output


def test_get_all_events_with_pagination_token(mocker, mock_client):
    """
    Given:
    - druva-get-all-events command with page_token

    When:
    - running get-all-events command with pagination token

    Then:
    - Ensure get_all_events is called with ONLY page_token
    - Ensure other filter parameters are NOT passed to API
    """
    mocker.patch.object(mock_client, "get_all_events", return_value=V3_RESPONSE_WITH_EVENTS)

    args = {
        "page_token": "eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ==",
        "product_id": "4097",  # This should be ignored
        "category": "ALERT",  # This should be ignored
        "should_push_events": "false",
    }

    result = druva_get_all_events_command(mock_client, args)

    # Verify API called with page_token and other parameters
    # Note: The command function passes all args, but the client method should ignore others
    mock_client.get_all_events.assert_called_once()
    call_args = mock_client.get_all_events.call_args
    assert call_args.kwargs["page_token"] == "eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ=="

    # Verify output
    assert result.outputs is not None
    outputs = result.outputs
    assert outputs["totalEvents"] == 2  # type: ignore[index]
    assert outputs["hasMore"] is True  # type: ignore[index]


def test_get_all_events_api_method_pagetoken_only(mocker, mock_client):
    """
    Given:
    - Client.get_all_events method with page_token

    When:
    - Calling get_all_events with page_token and other filters

    Then:
    - Ensure only pageToken parameter is sent to API
    - Ensure other filters are ignored as per API requirement
    """
    http_mock = mocker.patch.object(mock_client, "_http_request", return_value=V3_RESPONSE_WITH_EVENTS)

    # Call with page_token and other filters
    mock_client.get_all_events(product_id="4097", category="ALERT", page_token="test_token_123", page_size=100)

    # Verify that only pageToken was passed in params
    call_kwargs = http_mock.call_args.kwargs
    assert "params" in call_kwargs
    params = call_kwargs["params"]

    # Should ONLY have pageToken, no other params
    assert params == {"pageToken": "test_token_123"}
    assert "productID" not in params
    assert "category" not in params
    assert "pageSize" not in params


def test_get_all_events_api_method_with_filters(mocker, mock_client):
    """
    Given:
    - Client.get_all_events method with filters but NO page_token

    When:
    - Calling get_all_events with various filters

    Then:
    - Ensure all filter parameters are sent to API
    - Ensure correct endpoint is called
    """
    http_mock = mocker.patch.object(mock_client, "_http_request", return_value=V3_RESPONSE_WITH_EVENTS)

    mock_client.get_all_events(
        product_id="4097",
        syslog_severity="3",
        category="ALERT",
        event_type="Alert",
        feature="Alerts And Notifications",
        page_size=100,
    )

    # Verify correct endpoint
    call_kwargs = http_mock.call_args.kwargs
    assert call_kwargs["url_suffix"] == "/platform/eventmanagement/v3/events"

    # Verify all filter parameters are included
    params = call_kwargs["params"]
    assert params["productID"] == "4097"
    assert params["syslogSeverity"] == "3"
    assert params["category"] == "ALERT"
    assert params["type"] == "Alert"
    assert params["feature"] == "Alerts And Notifications"
    assert params["pageSize"] == "100"
    assert "pageToken" not in params


def test_add_time_to_events_v3():
    """
    Given:
    - v3 API events with timeStamp field (unix timestamp)

    When:
    - Calling add_time_to_events_v3 function

    Then:
    - Ensure _time field is added correctly
    - Ensure unix timestamp is converted to proper ISO format
    """
    events = [
        {
            "id": 840135132,
            "timeStamp": 1761894118,  # Unix timestamp
            "type": "Alert",
        },
        {"id": 840135133, "timeStamp": 1761894200, "type": "Event"},
    ]

    add_time_to_events_v3(events)

    # Verify _time field was added to all events
    assert "_time" in events[0]
    assert "_time" in events[1]

    # Verify timestamp format (should be in DATE_FORMAT)
    # Unix timestamp 1761894118 should convert to a valid date
    assert events[0]["_time"]  # Should be a valid date string
    assert events[1]["_time"]

    # Verify format is correct (YYYY-MM-DDTHH:MM:SSZ)
    import re

    date_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
    assert re.match(date_pattern, events[0]["_time"])
    assert re.match(date_pattern, events[1]["_time"])


def test_add_time_to_events_v3_missing_timestamp(mocker):
    """
    Given:
    - v3 API event without timeStamp field

    When:
    - Calling add_time_to_events_v3 function

    Then:
    - Ensure debug message is logged
    - Ensure no _time field is added
    - Ensure function doesn't crash
    """
    mock_debug = mocker.patch("DruvaEventCollector.demisto.debug")

    events = [
        {
            "id": 840135132,
            # Missing timeStamp field
            "type": "Alert",
        }
    ]

    # Should not raise exception
    add_time_to_events_v3(events)

    # Verify debug was called with appropriate message
    mock_debug.assert_called()
    debug_message = mock_debug.call_args[0][0]
    assert "no timeStamp field" in debug_message
    assert "840135132" in debug_message

    # Verify _time field was NOT added
    assert "_time" not in events[0]


def test_get_all_events_page_size_validation(mock_client):
    """
    Given:
    - druva-get-all-events command with invalid page_size (>500)

    When:
    - running get-all-events command

    Then:
    - Ensure DemistoException is raised with appropriate message
    """
    args = {
        "page_size": "600",  # Exceeds max of 500
        "should_push_events": "false",
    }

    with pytest.raises(DemistoException, match="page_size cannot exceed 500"):
        druva_get_all_events_command(mock_client, args)
