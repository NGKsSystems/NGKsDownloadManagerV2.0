<!-- markdownlint-disable -->

<!-- markdownlint-disable -->

# PROJECT SCOPE

## NGKs Download Manager V2.1

### Core Scope

Multi-connection HTTP/HTTPS downloader with GUI integration:
- 4-connection parallel downloads with range request detection
- Automatic single-connection fallback for non-range servers
- Interrupt/resume functionality with state persistence
- GUI progress callback integration (filename, progress, speed, status)
- Local test server for deterministic verification

### Verified Integration Points

- DownloadManager.download() API preserved
- Progress callback format: filename, progress, speed, status  
- Boolean return values for legacy compatibility
- Resume functionality via state file persistence

### Gate Criteria

V2.1 Release Gate: python test_v21_acceptance.py must show:
- Tests passed: 3/3
- OVERALL: PASS

All tests must exercise real functionality without fake passes.