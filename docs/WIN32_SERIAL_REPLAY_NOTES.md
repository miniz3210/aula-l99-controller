# Win32 serial replay implementation notes

Planned Windows serial I/O sequence:

1. Open the serial device with `CreateFileW("\\.\COM8")`.
2. Configure buffers with `SetupComm`.
3. Configure serial parameters with `SetCommState`.
4. Configure timeouts with `SetCommTimeouts`.
5. Send packets using `WriteFile` with overlapped I/O.
6. Wait for completion using `WaitForSingleObject`.
7. Inspect communication state and errors using `ClearCommError`.
8. Read device responses using `ReadFile`.

This is an implementation outline, not a completed or verified script.
