This is the Druva event collector integration for Cortex XSIAM.

## Configure Druva Event Collector in Cortex

| **Parameter** | **Required** |
| --- | --- |
| Server URL | True |
| Client ID | True |
| Secret Key | True |
| Trust any certificate (not secure) |  |
| Use system proxy settings |  |

## Commands

You can execute these commands from the CLI, as part of an automation, or in a playbook.
After you successfully execute a command, a DBot message appears in the War Room with the command details.

### druva-get-events

***
Gets events from Druva API in one batch (max 500). If tracker is given, only its successive events will be fetched.

#### Base Command

`druva-get-events`

#### Input

| **Argument Name** | **Description** | **Required** |
| --- | --- | --- |
| should_push_events | Set this argument to true in order to create Cortex XSIAM events, otherwise the command will only display them. Possible values are: true, false. Default is false. | Required |
| tracker | A string received in a previous run, marking the point in time from which we want to fetch. | Optional |

#### Context Output

There is no context output for this command.

### druva-get-all-events

***
Gets all events from Druva v3 Event Management API with advanced filtering capabilities. Supports pagination and can push events to XSIAM.

#### Base Command

`druva-get-all-events`

#### Input

| **Argument Name** | **Description** | **Required** |
| --- | --- | --- |
| product_id | Filter by product ID (e.g., "4097" for DCP, "8193" for inSync, "12289" for Phoenix). | Optional |
| syslog_severity | Filter by syslog severity level (0-7, where 3=Error, 4=Warning, 6=Informational). | Optional |
| category | Filter by event category. Possible values are: ALERT, AUDIT, EVENT. | Optional |
| type | Filter by event type. Possible values are: EVENT, ALERT. | Optional |
| feature | Filter by feature name (e.g., "Alerts And Notifications", "Ransomware Recovery"). | Optional |
| page_token | Pagination token received from a previous run to get the next page of results. **IMPORTANT**: When using page_token, do not pass any other filter parameters as the token already contains all filter information. | Optional |
| page_size | Number of events to retrieve per page (max 500). Default is 500. | Optional |
| should_push_events | When true, the integration creates Cortex XSIAM events. Otherwise, they will only be displayed. Possible values are: true, false. Default is false. | Optional |

#### Context Output

| **Path** | **Type** | **Description** |
| --- | --- | --- |
| Druva.AllEvents.events | Unknown | List of retrieved events. |
| Druva.AllEvents.nextPageToken | String | Token to use for retrieving the next page of results. Use this value as page_token parameter in the next call. Empty if no more pages available. |
| Druva.AllEvents.hasMore | Boolean | Indicates if more events are available. False when events list is empty (last page reached) or when nextPageToken is absent. |
| Druva.AllEvents.totalEvents | Number | Total number of events in the current response. |

#### Command Examples

```bash
!druva-get-all-events product_id="4097" page_size="100"
```

```bash
!druva-get-all-events product_id="4097" category="ALERT" syslog_severity="3"
```

```bash
!druva-get-all-events product_id="4097" feature="Alerts And Notifications" type="ALERT"
```

```bash
!druva-get-all-events page_token="eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ=="
```

```bash
!druva-get-all-events product_id="4097" category="ALERT" should_push_events="true"
```

#### Context Example

```json
{
    "Druva": {
        "AllEvents": {
            "events": [
                {
                    "id": 840135132,
                    "category": "EVENT",
                    "details": {
                        "location": "Pune,India",
                        "adminName": "Test Admin",
                        "alertName": "Admin Login Event - New Location",
                        "adminEmail": "test@example.com",
                        "loginResult": "Success",
                        "adminIPAddress": "192.0.2.1",
                        "adminLoginTime": "2025-10-31T07:01:58Z"
                    },
                    "feature": "Alerts And Notifications",
                    "globalID": "e0663cd2-1ff2-46dc-86fe-80de3bccfe74-10608",
                    "timeStamp": 1761894118,
                    "productID": 4097,
                    "syslogFacility": 1,
                    "syslogSeverity": 4,
                    "type": "Alert"
                }
            ],
            "nextPageToken": "eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ==",
            "hasMore": true,
            "totalEvents": 1
        }
    }
}
```

#### Human Readable Output

```markdown
### Druva - All Events
|id|productID|category|type|feature|syslogSeverity|timeStamp|globalID|
|---|---|---|---|---|---|---|---|
| 840135132 | 4097 | EVENT | Alert | Alerts And Notifications | 4 | 1761894118 | e0663cd2-1ff2-46dc-86fe-80de3bccfe74-10608 |

**Pagination**: More events available. Use `page_token=eyJsYXN0X2V2ZW50X2lkIjo4NDAxMzUxMzMsInBhZ2Vfc2l6ZSI6NTAwfQ==` to fetch the next page.

**Note**: When using `page_token`, do not pass other filter parameters as the token already contains all filter information.
```

## Additional Information

### API Reference

- **v2 API**: Used by `druva-get-events` command for backward compatibility
- **v3 API**: Used by `druva-get-all-events` command with enhanced filtering and pagination
- Full API documentation: <https://developer.druva.com/reference/cybersecurity-events>

### Pagination Best Practices

1. Start with your initial query using filters (product_id, category, etc.)
2. If `hasMore` is true, use the `nextPageToken` value from the response
3. When using `page_token`, **do not include any other filter parameters**
4. Continue fetching pages until `hasMore` is false or events list is empty
5. **Pagination terminates automatically** when the API returns an empty events array (indicating last page reached)

### Common Product IDs

- **4097**: DCP (Data Center Protection / Cybersecurity)
- **8193**: inSync (Endpoint Backup)
- **12289**: Phoenix (Cloud Workloads)
- Refer to Druva documentation for other product IDs

### Syslog Severity Levels

- **0**: Emergency
- **1**: Alert
- **2**: Critical
- **3**: Error
- **4**: Warning
- **5**: Notice
- **6**: Informational
- **7**: Debug
