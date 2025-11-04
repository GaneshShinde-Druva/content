import base64
from urllib.parse import quote

import demistomock as demisto
import urllib3
from CommonServerPython import *

MIN_FETCH = 1
MAX_FETCH = 10_000
MAX_EVENTS_API_CALL = 500  # As a limitation of the API, we can only retrieve 500 events at a time
# Disable insecure warnings
urllib3.disable_warnings()

""" CONSTANTS """

DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT_FOR_TOKEN = "%m/%d/%Y, %H:%M:%S"
VENDOR = "Druva"
PRODUCT = "Druva"

""" CLIENT CLASS """


class Client(BaseClient):
    def __init__(self, base_url: str, client_id: str, secret_key: str, max_fetch: int, verify: bool, proxy: bool):
        super().__init__(base_url=base_url, verify=verify, proxy=proxy)
        self.credentials = f"{client_id}:{secret_key}"
        self.max_fetch = max_fetch
        self._max_fetch_validation()
        self.login()

    def login(self):
        """
        In this method, the validity of the Access Token is checked, since the Access Token has a 30 minutes validity period.
        Refreshes the token as needed.
        """
        now = datetime.utcnow()

        if (cache := get_integration_context()) and (token := cache.get("Token")):
            expiration_time = datetime.strptime(cache["expiration_time"], DATE_FORMAT_FOR_TOKEN)

            # check if token is still valid, and use the old one. otherwise regenerate a new one
            if (seconds_left := (expiration_time - now).total_seconds()) > 0:
                demisto.debug(f"No need to regenerate the token, it is still valid for {seconds_left} more seconds")
                self._set_headers(token)
                return

        demisto.debug("IntegrationContext token cache is empty or token has expired, regenerating a new token")
        raw_token, expires_in_seconds = self._refresh_access_token()
        self._set_headers(raw_token)

        set_integration_context(
            {
                "Token": raw_token,
                "expiration_time": (
                    now + timedelta(seconds=(expires_in_seconds - 60))  # decreasing 60s from token expiry for safety
                ).strftime(DATE_FORMAT_FOR_TOKEN),
            }
        )

    def _refresh_access_token(self) -> tuple[str, int]:
        """
        Since the validity of the Access Token is 30 minutes, this method refreshes it and returns the new token json.
        returns:
            - the token
            - the expiration in seconds
        """
        credentials = base64.b64encode(self.credentials.encode()).decode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        }
        data = {"grant_type": "client_credentials", "scope": "read"}

        try:
            response_json = self._http_request(method="POST", url_suffix="/token", headers=headers, data=data)
        except Exception as e:
            # 400 - "invalid_grant" - reason: invalid Server URL, Client ID or Secret Key.
            if "invalid_grant" in str(e):
                raise DemistoException(
                    "Error in test-module: Make sure Server URL, Client ID and Secret Key are correctly entered."
                ) from e
            raise
        return response_json["access_token"], response_json["expires_in"]

    def search_events(self, tracker: Optional[str] = None) -> dict:
        """
        Searches for Druva events.

        Args:
            tracker: pointer to the last event we got last time

        Returns:
            dict: List of events
        """
        demisto.debug(f"This is the tracker before encoding: {tracker=}")

        if tracker:
            encoding_tracker = quote(tracker, safe="!~*'()")  # remove invalid characters from tracker
            demisto.debug(f"after encoding: {encoding_tracker=}")
            url_suffix_tracker = f"?tracker={encoding_tracker}"
        else:
            url_suffix_tracker = ""

        headers = (self._headers or {}) | {"accept": "application/json"}  # self._headers won't really be None, just for mypy
        try:
            response = self._http_request(
                method="GET",
                url_suffix=f"/insync/eventmanagement/v2/events{url_suffix_tracker}",
                headers=headers,
            )
        except Exception as e:
            # 403 - "User is not authorized to access this resource with an explicit deny" - reason: tracker is expired
            # 400 - "Invalid tracker"
            raise DemistoException(f"Error in search-events: {e!s}") from e
        return response

    def _set_headers(self, token: str):
        """
        This method is called during the client's building or when a new token is generated since the old one has expired.
        """
        self._headers = {"Authorization": f"Bearer {token}"}

    def _max_fetch_validation(self):
        if self.max_fetch > MAX_FETCH or self.max_fetch < MIN_FETCH:
            raise DemistoException(f"The maximum number of events per fetch should be between 1 - {MAX_FETCH}")

    def get_all_events(
        self,
        product_id: Optional[str] = None,
        syslog_severity: Optional[str] = None,
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        feature: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 500,
    ) -> dict:
        """
        Gets all events from Druva v3 Event Management API with filtering capabilities.
        Reference: https://developer.druva.com/reference/cybersecurity-events

        Args:
            product_id: Filter by product ID (e.g., "4097" for DCP, "8193" for inSync, "12289" for Phoenix)
            syslog_severity: Filter by syslog severity level (0-7, e.g., "3" for Error)
            category: Filter by event category (e.g., "ALERT", "EVENT", "AUDIT")
            event_type: Filter by event type (e.g., "Alert", "Backup")
            feature: Filter by feature (e.g., "Alerts And Notifications", "Ransomware Recovery")
            page_token: Token for pagination to get next page of results
                        NOTE: When page_token is provided, all other filters are ignored
                        as the token contains the complete filter state
            page_size: Number of events per page (max 500)

        Returns:
            dict: Response containing events and pagination info
        """
        params: dict[str, Any] = {}

        # IMPORTANT: When pageToken is provided, it should be used alone
        # The token already contains all filter information from the previous call
        if page_token:
            demisto.debug("Using pageToken for pagination. All other filters will be ignored.")
            params["pageToken"] = page_token
            # Note: pageSize is also encoded in the token, so we don't add it
        else:
            # Add filter parameters only when not using pageToken
            if product_id:
                params["productID"] = product_id
            if syslog_severity:
                params["syslogSeverity"] = syslog_severity
            if category:
                params["category"] = category
            if event_type:
                params["type"] = event_type
            if feature:
                params["feature"] = feature
            if page_size:
                params["pageSize"] = str(page_size)

            demisto.debug(f"Fetching events with filters: {params}")

        headers = (self._headers or {}) | {"accept": "application/json"}

        try:
            response = self._http_request(
                method="GET",
                url_suffix="/platform/eventmanagement/v3/events",
                headers=headers,
                params=params,
            )
        except Exception as e:
            raise DemistoException(f"Error in get-all-events: {e!s}") from e

        return response


def test_module(client: Client) -> str:
    """
    Tests API connectivity and authentication
    When 'ok' is returned it indicates the integration works like it is supposed to and connection to the service is
    successful.
    Raises exceptions if something goes wrong.

    Args:
        client (Client): Druva client to use.
    Returns:
        str: 'ok' if test passed, anything else will raise an exception and will fail the test.
    """
    get_events(client=client)
    return "ok"


def get_events(client: Client, tracker: Optional[str] = None) -> tuple[list[dict], str]:
    """
    Gets events from Druva API in one batch (max 500), if a tracker is given, the API returns events starting from its timestamp.
    There will be no changes to the tracker if no events occur.
    Args:
        client: Druva client to use.
        tracker: A string received in a previous run, marking the point in time from which we want to fetch.

    Returns:
        Druva's events and tracker
    """

    response = client.search_events(tracker)

    return response["events"], response["tracker"]


def fetch_events(client: Client, last_run: dict[str, str], max_fetch: int) -> tuple[list[dict], dict[str, str]]:
    """
    Args:
        client (Client): Druva client to use.
        last_run (dict): A dict with a key containing a pointer to the latest event created time we got from last fetch.
        max_fetch (int): The maximum number of events per fetch.
    Returns:
        last_run (dict): A dict containing the next tracker (a pointer to the next event).
        events (list): List of events that will be created in XSIAM.
    """
    demisto.debug(f"Last Run: {last_run}")
    final_events: list[dict] = []
    done_fetching: bool = False
    while len(final_events) < max_fetch and not done_fetching:
        tracker = last_run.get("tracker")  # None on first run
        # when fetching events, in case of "Invalid tracker", we catch the exception and restore the same tracker
        try:
            events, new_tracker = get_events(client, tracker)
        except Exception as e:
            if "Invalid tracker" in str(e):
                demisto.debug(
                    "The tracker is invalid, catching the error and continuing with the same tracker for the next time."
                )
                events, new_tracker = [], tracker  # type:ignore[assignment]
            else:
                raise e

        # It means there are no more events to retrieve when there are fewer than 500 events
        done_fetching = len(events) < MAX_EVENTS_API_CALL

        # Save the next_run as a dict with the last_fetch key to be stored
        next_run = {"tracker": new_tracker or ""}
        last_run = next_run
        final_events.extend(events)

    return final_events, last_run


def druva_get_all_events_command(client: Client, args: dict[str, Any]) -> CommandResults:
    """
    Retrieves events from Druva v3 Event Management API with filtering capabilities.
    Reference: https://developer.druva.com/reference/cybersecurity-events

    Args:
        client: Druva client to use
        args: Command arguments from Demisto
            - product_id: Filter by product ID (e.g., "4097" for DCP, "8193" for inSync, "12289" for Phoenix)
            - syslog_severity: Filter by syslog severity level (0-7)
            - category: Filter by event category (e.g., ALERT, AUDIT, EVENT)
            - type: Filter by event type (e.g., Alert, Backup)
            - feature: Filter by feature name (e.g., "Alerts And Notifications")
            - page_token: Token for pagination
            - page_size: Number of events per page (default 500, max 500)
            - should_push_events: Whether to push events to XSIAM (true/false)

    Returns:
        CommandResults: Contains events in human readable format and context data
    """
    # Extract arguments
    product_id = args.get("product_id")
    syslog_severity = args.get("syslog_severity")
    category = args.get("category")
    event_type = args.get("type")
    feature = args.get("feature")
    page_token = args.get("page_token")
    page_size = arg_to_number(args.get("page_size", 500)) or 500
    should_push_events = argToBoolean(args.get("should_push_events", False))

    # Validate page_size
    if page_size > 500:
        raise DemistoException("page_size cannot exceed 500")

    demisto.debug(
        f"druva-get-all-events called with: product_id={product_id}, "
        f"syslog_severity={syslog_severity}, category={category}, type={event_type}, "
        f"feature={feature}, page_size={page_size}"
    )

    # Call the API
    response = client.get_all_events(
        product_id=product_id,
        syslog_severity=syslog_severity,
        category=category,
        event_type=event_type,
        feature=feature,
        page_token=page_token,
        page_size=page_size,
    )

    events = response.get("events", [])
    # API returns 'nextPageToken'
    next_page_token = response.get("nextPageToken", "")

    # If events list is empty, we've hit the last page (terminate pagination)
    # API may return nextPageToken even with empty array, but empty array means last page
    if not events:
        next_page_token = ""
        has_more = False
    else:
        has_more = bool(next_page_token)

    demisto.debug(f"Retrieved {len(events)} events. hasMore={has_more}, nextPageToken={'present' if next_page_token else 'none'}")

    # Prepare human readable output
    hr_title = f"{VENDOR} - All Events"
    if events:
        # Event structure: id, category, details, feature, globalID, timeStamp, productID, syslogFacility, syslogSeverity, type
        hr = tableToMarkdown(
            hr_title,
            events,
            headers=[
                "id", "productID", "category", "type", "feature",
                "syslogSeverity", "syslogFacility", "timeStamp", "globalID", "details"
            ],
            removeNull=True,
        )
    else:
        hr = f"### {hr_title}\nNo events found with the specified filters."

    # Add pagination info to human readable
    if has_more:
        hr += f"\n\n**Pagination**: More events available. Use `page_token={next_page_token}` to fetch the next page."
        hr += (
            "\n\n **Note**: When using `page_token`, do not pass other filter parameters "
            "as the token already contains all filter information."
        )
    else:
        hr += "\n\n**Pagination**: No more events available."

    # Prepare context output
    context_output = {
        "events": events,
        "nextPageToken": next_page_token,
        "hasMore": has_more,
        "totalEvents": len(events),
    }

    # Push events to XSIAM if requested
    if should_push_events and events:
        add_time_to_events_v3(events)
        send_events_to_xsiam(events, vendor=VENDOR, product=PRODUCT)
        hr += f"\n\n **{len(events)} events pushed to XSIAM successfully.**"

    return CommandResults(
        readable_output=hr,
        outputs_prefix=f"{VENDOR}.AllEvents",
        outputs_key_field="eventID",
        outputs=context_output,
    )


""" MAIN FUNCTION """


def add_time_to_events(events: list[dict]):
    """
    Adds the _time key to the events.
    Args:
        events: list[dict] - list of events to add the _time key to.
    Returns:
        list: The events with the _time key.
    """
    if events:
        for event in events:
            create_time = arg_to_datetime(event["timestamp"])
            event["_time"] = create_time.strftime(DATE_FORMAT)  # type: ignore[union-attr]


def add_time_to_events_v3(events: list[dict]):
    """
    Adds the _time key to the events from v3 API.
    v3 API uses 'timeStamp' field with unix timestamp (integer).

    Args:
        events: list[dict] - list of v3 events to add the _time key to.
    Returns:
        list: The events with the _time key.
    """
    if events:
        for event in events:
            if "timeStamp" in event:
                # v3 API: convert unix timestamp to datetime
                create_time = datetime.fromtimestamp(event["timeStamp"], tz=timezone.utc)
                event["_time"] = create_time.strftime(DATE_FORMAT)
            else:
                demisto.debug(f"v3 Event has no timeStamp field: {event.get('id', 'unknown')}")


def main() -> None:  # pragma: no cover
    """
    main function, parses params and runs command functions
    """

    params = demisto.params()
    args = demisto.args()
    command = demisto.command()
    proxy = params.get("proxy", False)
    verify_certificate = not params.get("insecure", False)
    max_fetch = arg_to_number(params.get("max_fetch")) or MAX_FETCH

    demisto.debug(f"Command being called is {command}")
    try:
        client = Client(
            base_url=params["url"],
            client_id=params["credentials"]["identifier"],
            secret_key=params["credentials"]["password"],
            max_fetch=max_fetch,
            verify=verify_certificate,
            proxy=proxy,
        )

        if command == "test-module":
            # This is the call made when pressing the integration Test button.
            return_results(test_module(client))

        elif command == "druva-get-events":
            events, tracker = get_events(client, args.get("tracker"))
            return_results(
                CommandResults(
                    readable_output=tableToMarkdown(f"{VENDOR} Events:", events),
                    outputs=tracker,
                    outputs_prefix=f"{VENDOR}.tracker",
                    outputs_key_field="tracker",
                    replace_existing=True,
                )
            )
            if argToBoolean(args["should_push_events"]):
                add_time_to_events(events)
                send_events_to_xsiam(events, vendor=VENDOR, product=PRODUCT)

        elif command == "druva-get-all-events":
            return_results(druva_get_all_events_command(client, args))

        elif command == "fetch-events":
            events, next_run = fetch_events(client=client, last_run=demisto.getLastRun(), max_fetch=max_fetch)

            add_time_to_events(events)
            send_events_to_xsiam(events, vendor=VENDOR, product=PRODUCT)

            demisto.debug(f"fetched {len(events or [])} events. Setting {next_run=}.")
            demisto.setLastRun(next_run)

    # Log exceptions and return errors
    except Exception as e:
        return_error(f"Failed to execute {command} command.\nError:\n{e!s}")


""" ENTRY POINT """

if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
