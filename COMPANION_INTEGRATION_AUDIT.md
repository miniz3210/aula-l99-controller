# AULA L99 — Companion Integration Safety and Test Coverage Audit

**Repository:** C:\temp\aula-l99-controller
**HEAD:** 65d0719
**Mode:** READ-ONLY
**Date:** 2026-11-14

---

## 1. Git Baseline

```
HEAD: 65d071981ddc132758cf0dd4d11ad34735990856
Branch: main
Status: Clean (untracked files only - test artifacts and new companion modules)
```

**Untracked companion modules (new since baseline):**
- src/aula_bridge/companion_button_mapping.py
- src/aula_bridge/companion_dispatch_adapter.py
- src/aula_bridge/companion_http_transport.py
- src/aula_bridge/companion_http_sender.py
- src/aula_bridge/companion_transport.py
- src/aula_bridge/companion_types.py
- tests/test_companion_button_mapping.py
- tests/test_companion_dispatch_adapter.py
- tests/test_companion_dispatcher_integration.py
- tests/test_companion_http_transport.py
- tests/test_companion_http_sender.py
- tests/test_companion_offline_e2e.py
- tests/test_mock_companion_transport.py

---

## 2. Verified Safety Properties

### 2.1 Short-press-only behavior (VERIFIED)
- **CompanionDispatchAdapter** processes ONLY `short_press` events (line 56-65)
- `hold`, `secondary_hold`, `key_down`, `key_up`, `repeat_ignored` are explicitly ignored with debug logging
- Tests confirm: `test_hold_ignored`, `test_secondary_hold_ignored`, `test_key_down_ignored`, `test_key_up_ignored`, `test_repeat_ignored_ignored` all PASS
- E2E tests: `test_hold_generates_no_request`, `test_secondary_hold_generates_no_request`, `test_key_down_key_up_generate_no_request` all PASS

### 2.2 Hold and secondary_hold suppression (VERIFIED)
- Same as above: all hold-type events produce **zero HTTP requests**
- No command/payload sent to transport for these event types
- ActionDispatcher default mappings include hold/secondary_hold but adapter filters them out

### 2.3 Device identity preservation (VERIFIED)
- ProviderEvent.device field preserved throughout chain (not mutated)
- Adapter logs device identity in INFO logs: `device=0C45:800A` or `device=EEEF:268A`
- Tests: `test_device_identity_preserved`, `test_correct_source_device_identity`, `test_device_identity_preserved_in_logs` all PASS
- Transport metadata includes device field (MockCompanionTransport:98, test_companion_dispatcher_integration.py:312)

### 2.4 Event sequence preservation (VERIFIED)
- ProviderEvent.seq never mutated (frozen dataclass semantics)
- Adapter processes events in call order, dispatches in same order
- Mock transport records action_ids in dispatch order
- Tests: `test_event_sequence_preserved`, `test_correct_event_sequence`, `test_dispatch_ordering_preserved`, `test_multiple_actions_preserve_ordering`, `test_multiple_events_preserve_ordering` all PASS

### 2.5 HTTP response logging (VERIFIED)
- CompanionDispatchAdapter._log_response logs: key, device, seq, event, status_code, success, error_code
- All HTTP status codes mapped to semantic error codes: 200→success, 204→NO_CONTROL, 400→INVALID_LOCATION, 403→FORBIDDEN, 4xx→CLIENT_ERROR, 5xx→SERVER_ERROR, others→UNEXPECTED_STATUS
- ConnectionRefusedError→CONNECTION_REFUSED, TimeoutError→TIMEOUT, other OSError→CONNECTION_ERROR
- Tests: `test_http_200_accepted`, `test_http_204_reported_as_no_control`, `test_http_400_reported_as_invalid_location`, `test_http_403_reported_as_forbidden`, `test_http_500_reported_as_server_error`, `test_connection_refused_handled`, `test_timeout_handled` all PASS

### 2.6 HTTP failure handling (VERIFIED)
- All non-200 responses produce HttpResponse with success=False and appropriate error_code
- No exceptions propagate; all caught and converted to HttpResponse
- Sender returns HttpResponse for all error paths (HTTPError, URLError, TimeoutError, ConnectionRefusedError, OSError)
- Tests cover all status code ranges and connection error types

### 2.7 No default button mappings (VERIFIED)
- load_companion_button_mapping requires explicit mapping file
- Empty mappings object returns empty MappingProxyType
- No automatic/default locations invented for any key
- Tests: `test_empty_mapping`, `test_partial_mapping`, `test_no_default_actions`, `test_unmapped_short_press_no_request`, `test_no_default_mapping_invented`, `test_empty_mapping_generates_no_request`, `test_unmapped_key_generates_no_request` all PASS

### 2.8 Strict JSON validation (VERIFIED)
- Duplicate JSON keys rejected via object_pairs_hook (_reject_duplicates)
- Version must be integer, only version 1 supported
- All location fields (page, row, column) must be integers (bool, float, string rejected)
- Negative values rejected (page>=1, row>=0, column>=0)
- Unknown logical keys rejected (must be in NUM_PAD_KEYS)
- Extra/unknown fields in location object rejected
- Missing required fields rejected
- Top-level JSON must be object, mappings must be object
- Malformed JSON rejected with clear error
- Tests cover ALL validation paths (28 test methods in test_companion_button_mapping.py)

### 2.9 No automatic retries (VERIFIED)
- CompanionHttpTransport.press makes exactly ONE call to sender
- CompanionHttpSender._send_once makes exactly ONE opener.open() call
- _NoRedirectHandler returns None for all redirect codes (301,302,303,307,308)
- Tests: `test_no_automatic_retries` (transport, sender, adapter, E2E all PASS), `test_no_redirect_follow_up`, `test_no_retries_single_call` all PASS

### 2.10 No event buffering (VERIFIED)
- Each send() call processes exactly one event
- Transport.flush() and close() are no-ops
- No internal queues or buffers in adapter, transport, or sender
- Tests: `test_no_event_buffering` (transport, adapter, E2E all PASS)

### 2.11 No background threads (VERIFIED)
- All calls synchronous; press() returns only after sender completes
- No threading, asyncio, or concurrent.futures usage
- Tests: `test_no_background_threads` (transport, adapter, E2E all PASS)

### 2.12 No accidental live network activation (VERIFIED)
- All tests use FakeHttpSender / MockCompanionTransport
- CompanionHttpSender validates host is loopback (127.0.0.1) before any connection
- Non-loopback hosts rejected at sender level (NON_LOOPBACK_HOST)
- Scheme validation: only http:// allowed (https, ftp, file, ws rejected)
- No network access in any test (199 tests PASS with fake senders only)

### 2.13 No firmware/hardware access (VERIFIED)
- Zero imports of serial, usb, hid, or hardware libraries in companion modules
- All modules pure Python with dependency injection for testing
- Transport protocol is abstract interface (no I/O)

### 2.14 No modification of accepted Bridge behavior (VERIFIED)
- ActionDispatcher unchanged; companion adapter implements Transport protocol
- ProviderEvent unchanged (frozen dataclass semantics)
- DryRunProvider unchanged
- Default action mappings include hold/secondary_hold but adapter filters them

### 2.15 No hidden dependency on default port (VERIFIED)
- CompanionHttpTransport requires explicit host/port in constructor
- Defaults exist (127.0.0.1:5000) but can be overridden
- E2E tests use explicit TEST_PORT=19876 (never assumes 5000 or 8000)
- test_correct_companion_location_endpoint verifies explicit port in URL

---

## 3. HTTP Sender Security Behavior (Session B Repair)

### Redirect rejection (VERIFIED)
- _NoRedirectHandler.redirect_request returns None for ALL redirect codes (301,302,303,307,308)
- Tests: test_redirect_301_rejected through test_redirect_308_rejected all PASS
- No follow-up requests (test_no_redirect_follow_up: open_calls == 1)

### Scheme validation (VERIFIED)
- Only http:// scheme permitted (_parse_host line 53)
- https://, ftp://, file://, ws://, and unsupported schemes rejected as INVALID_URL
- Tests: test_https_scheme_rejected, test_ftp_scheme_rejected, test_file_scheme_rejected, test_unsupported_scheme_rejected all PASS

### URL userinfo rejection (VERIFIED)
- Username/password in URL rejected (_parse_host lines 56-58)
- Credentials never appear in error messages (test_no_credential_leakage PASS)
- Both user:pass@ and user@ forms rejected
- Tests: test_url_userinfo_rejected, test_url_username_only_rejected PASS

### Unexpected path/query/fragment rejection (VERIFIED)
- Fragment (#section) rejected (test_url_fragment_rejected PASS)
- Query parameters (?foo=bar) rejected (test_url_query_rejected PASS)
- Path must match ^/api/location/(\d+)/(\d+)/(\d+)/press$ (_PRESS_ENDPOINT_RE)
- Wrong path (/api/other/...) rejected (test_invalid_endpoint_path_rejected PASS)
- Missing /press suffix rejected (test_missing_press_suffix_rejected PASS)

### Loopback-only restriction (VERIFIED)
- _validate_host uses ipaddress.ip_address().is_loopback (transport line 100)
- Sender re-validates host is loopback (sender line 127)
- 127.0.0.1 allowed; localhost rejected (not numeric IP); 192.168.x.x, 8.8.8.8, example.com rejected
- Tests: test_loopback_127_0_0_1_allowed, test_localhost_rejected, test_remote_ipv4_rejected, test_remote_public_ip_rejected, test_remote_domain_rejected all PASS

---

## 4. Remaining Risks

| # | Risk | Classification | Details |
|---|------|----------------|---------|
| 1 | **No integration test with real Companion instance** | UNKNOWN | All tests use fakes; real API behavior (rate limits, auth, schema changes) untested |
| 2 | **Button mapping file not hot-reloadable** | INFERENCE | Mapping loaded once at startup; file changes require restart |
| 3 | **No authentication support** | INFERENCE | Companion HTTP API may require auth token; not implemented |
| 4 | **Single-threaded synchronous HTTP** | INFERENCE | Blocking I/O; could stall bridge if Companion unresponsive (timeout mitigates) |
| 5 | **No health check / connection verification** | INFERENCE | No pre-flight check that Companion is reachable before dispatch |
| 6 | **Error codes not mapped to user actions** | INFERENCE | Logs errors but no retry/backoff/alerting strategy defined |
| 7 | **No encryption (HTTP only)** | VERIFIED | http:// only; loopback mitigates but not defense-in-depth |
| 8 | **Fixed 5s default timeout** | INFERENCE | May be too short for slow networks / loaded Companion |
| 9 | **No circuit breaker** | INFERENCE | Repeated failures don't pause dispatch; could log spam |

---

## 5. Missing Test Coverage

| Area | Status | Gap |
|------|--------|-----|
| Real Companion API integration | UNKNOWN | No live tests; all mocked |
| Authentication flow | UNKNOWN | Not implemented, not tested |
| Hot reload of mapping file | UNKNOWN | Not implemented |
| Concurrent event dispatch | UNKNOWN | Single-threaded; no concurrency tests |
| Large event bursts | INFERENCE | No stress/load tests |
| Network partition behavior | UNKNOWN | Only ConnectionRefused/Timeout tested |
| Companion API version compatibility | UNKNOWN | Tests assume 5.2.0 press endpoint |
| TLS/HTTPS support | VERIFIED ABSENT | Explicitly rejected by design |
| Metrics / observability | UNKNOWN | Only logging; no Prometheus/OpenTelemetry |
| Graceful shutdown with in-flight requests | UNKNOWN | close() is no-op |

---

## 6. Required Corrections

**None required.** All 199 tests pass. Implementation meets all stated safety requirements:
- Short-press only ✓
- Hold/secondary_hold suppressed ✓
- Device identity preserved ✓
- Event sequence preserved ✓
- HTTP response logging ✓
- HTTP failure handling ✓
- No default mappings ✓
- Strict JSON validation ✓
- No auto retries ✓
- No buffering ✓
- No background threads ✓
- No live network ✓
- No firmware/hardware access ✓
- No bridge behavior modification ✓
- No hidden port dependency ✓
- HTTP sender security (redirects, scheme, userinfo, path/query/fragment, loopback) ✓

---

## 7. Acceptance Recommendation

**ACCEPT** — Companion integration is **safe for offline development and testing**.

### Conditions for production use:
1. Add authentication support if Companion requires it
2. Implement health check endpoint before dispatch
3. Add circuit breaker for repeated failures
4. Consider HTTPS support for defense-in-depth
5. Conduct live integration test with real Companion 5.2.0+

### Current state suitable for:
- Offline unit/integration testing (complete)
- Dry-run development with DryRunProvider
- Mock transport validation
- Mapping configuration validation

### Not yet suitable for:
- Production deployment with live Companion
- Unattended operation without monitoring
- Networks where loopback isolation insufficient

---

## Classification Summary

| Property | Classification |
|----------|----------------|
| Short-press-only behavior | VERIFIED |
| Hold/secondary_hold suppression | VERIFIED |
| Device identity preservation | VERIFIED |
| Event sequence preservation | VERIFIED |
| HTTP response logging | VERIFIED |
| HTTP failure handling | VERIFIED |
| No default button mappings | VERIFIED |
| Strict JSON validation | VERIFIED |
| No automatic retries | VERIFIED |
| No event buffering | VERIFIED |
| No background threads | VERIFIED |
| No accidental live network | VERIFIED |
| No firmware/hardware access | VERIFIED |
| No bridge behavior modification | VERIFIED |
| No hidden port dependency | VERIFIED |
| HTTP sender: redirect rejection | VERIFIED |
| HTTP sender: scheme validation | VERIFIED |
| HTTP sender: userinfo rejection | VERIFIED |
| HTTP sender: path/query/fragment rejection | VERIFIED |
| HTTP sender: loopback-only restriction | VERIFIED |
| Real Companion integration | UNKNOWN |
| Authentication support | UNKNOWN |
| Hot reload | UNKNOWN |
| Production readiness | INFERENCE (NOT READY) |