# Urja Meter Ops — Protocol & Reverse-Engineering Discovery

**Document Version:** 1.0.0  
**Target Host:** `https://urja-ops.flockenergy.tech`  
**Inspected Date:** October 2026  
**Audience:** Internal Engineering & Technical Reviewers  

---

## 1. Executive Summary

The **Urja Meter Ops** platform is a modern Single Page Application (SPA) built with **SvelteKit** and bundled via **Vite**, backed by a server running **better-auth** session management.

Although presented in the assignment description as a legacy portal needing HTML scraping, in-depth network and JavaScript bundle reconnaissance revealed a hybrid operational surface:
1. **CSRF-Protected Web Form Action** (`/login`) backed by `better-auth`.
2. **Internal JSON REST Endpoints** (`/portal/...`) consumed by client-side SvelteKit components for searches, geographic data, and time-series energy consumption.
3. **Server-Side Rendered (SSR) SvelteKit Data Nodes** (`/meters/[id]/__data.json`) that pass dehydrated state containing nameplate attributes and grid network hierarchy.
4. **An HMAC-SHA256 Signed Bulk Export Pipeline** (`/portal/export`) guarded by ephemeral signing keys fetched from `/portal/keys`.

---

## 2. Authentication & Session Architecture

### 2.1 The Login Flow
* **URL:** `POST https://urja-ops.flockenergy.tech/login`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Payload:**
  ```urlencoded
  email=operator%40urja.local&password=urja-ops-2026
  ```

### 2.2 SvelteKit CSRF Trap & Fix
* **Quirk / Hurdle:** Direct `POST` submissions without specific browser headers fail immediately with **`403 Forbidden`** and plain text body:
  `Cross-site POST form submissions are forbidden`.
* **Root Cause:** SvelteKit validates that incoming requests contain an `Origin` header matching the host domain.
* **Solution:** The client adapter must explicitly inject:
  ```http
  Origin: https://urja-ops.flockenergy.tech
  Referer: https://urja-ops.flockenergy.tech/login
  ```

### 2.3 Session Lifecycle & Cookies
* Upon valid credentials, the server responds with **`200 OK`** and a JSON redirect command:
  ```json
  {"type": "redirect", "status": 303, "location": "/meters"}
  ```
* Sets an `HttpOnly`, `Secure` cookie:
  ```http
  Set-Cookie: __Secure-better-auth.session_token=<token>; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax
  ```
* **Session Lifetime:** Exactly 3600 seconds (1 hour).
* **Unauthorized Behavior:** All subsequent protected calls return `401 Unauthorized` (`{"error": "unauthorized", "message": "A valid session is required."}`) once this cookie expires.
* **Auto-Reauthentication Requirement:** The adapter must detect HTTP 401, re-execute the handshake transparently, update cookie storage, and retry the failed upstream request.

---

## 3. Discovered Internal APIs & Endpoints

| Endpoint | Method | Auth Required | Purpose & Details |
| :--- | :--- | :--- | :--- |
| `/login` | `POST` | No | Submits operator credentials; issues session token. |
| `/api/auth/sign-out` | `POST` | Yes | Invalidates active session. |
| `/portal/meters/search` | `GET` | Yes | Paginated search across meters (`q`, `page`). |
| `/portal/meters/{id}/geo` | `GET` | Yes | Returns GPS coordinates for a specific meter. |
| `/portal/meters/{id}/energy`| `GET` | Yes | Returns 30-min interval time-series readings. |
| `/meters/{id}/__data.json` | `GET` | Yes | SvelteKit dehydrated server state (nameplate & hierarchy). |
| `/portal/dts` | `GET` | Yes | Paginated list of Distribution Transformers (DTs). |
| `/portal/keys` | `GET` | Yes | Retrieves current signing secret for bulk exports. |
| `/portal/export` | `GET` | Yes + HMAC | Cryptographically signed endpoint returning the entire grid inventory. |

---

## 4. Deep Dive: Discovered Endpoints & Payloads

### 4.1 Meter Search (`GET /portal/meters/search`)
* **Query Parameters:**
  * `q` (string): Filters against `meterId` or `serialNo`. (*Note: Does not filter across make, status, or hierarchy*).
  * `page` (integer): 1-indexed page number.
* **Response Shape:**
  ```json
  {
    "total": 403,
    "data": [
      {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "dtCode": "DT-001"
      }
    ]
  }
  ```
* **Quirks & Limitations:**
  * Page size is strictly hardcoded to 20 items on the server; passing `limit` or `pageSize` is ignored.
  * Search queries like `HPL` or `single` return 0 results.

### 4.2 Meter Geographic Coordinates (`GET /portal/meters/{id}/geo`)
* **Response Shape:**
  ```json
  {
    "data": {
      "latitude": "26.938961002479868",
      "longitude": "75.83095696146852"
    }
  }
  ```
* **Anomaly:** Floating-point coordinates are transmitted as raw strings. The adapter must cast them into true floats with bounds checking.

### 4.3 Meter Energy Readings (`GET /portal/meters/{id}/energy`)
* **Response Shape:**
  ```json
  {
    "data": [
      {
        "timestamp": "23/06/2026 23:30",
        "kwh": "48438.74",
        "kvah": "52313.84",
        "voltR": "226"
      }
    ]
  }
  ```
* **Data Inconsistencies:**
  * Timestamps follow Indian/British format `DD/MM/YYYY HH:MM`. Must be standardized to ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`).
  * `kwh`, `kvah`, and `voltR` are string-encoded numbers. In empty or error states, values can be empty strings `""` or em-dashes `" — "`.

### 4.4 Distribution Transformers (`GET /portal/dts`)
* **Query Parameters:** `page` (1-indexed).
* **Dataset Size:** 40 DT records across 2 pages.
* **Response Shape:**
  ```json
  {
    "total": 40,
    "data": [
      {
        "code": "DT-001",
        "name": "Malviya Nagar DT 1",
        "feederCode": "F-001",
        "capacityKva": 100
      }
    ]
  }
  ```

---

## 5. Critical Discovery: Nameplate Schema Divergence (Legacy vs. v2)

When querying individual meter detail via SvelteKit's SSR data node (`/meters/{id}/__data.json`), the data structure bifurcates based on the internal `build` attribute of the meter:

```mermaid
graph TD
    A[Meter Detail Request] --> B{Meter Build Variant}
    B -->|build = 'legacy' 238 meters| C[Parameter List Schema]
    B -->|build = 'v2' 165 meters| D[classData JSON String Schema]
    C --> E[data: array of {parameterName, parameterValue}]
    D --> F[classData: string containing {installed_meter: {PascalCase}}]
    E --> G[Unified Pydantic Model]
    F --> G
```

1. **Legacy Meters (`build == 'legacy'`)**:
   Detail data is serialized as a flat list of key-value pairs:
   ```json
   {
     "data": [
       {"parameterName": "Meter ID", "parameterValue": "J100000"},
       {"parameterName": "Serial No", "parameterValue": "SE33962"},
       {"parameterName": "Make", "parameterValue": "HPL"},
       {"parameterName": "Phase Type", "parameterValue": "single"},
       {"parameterName": "Installation Status", "parameterValue": "Decommissioned"},
       {"parameterName": "Installation Type", "parameterValue": "Whole Current"}
     ]
   }
   ```
2. **v2 Modernized Meters (`build == 'v2'`)**:
   Detail data is nested as an escaped JSON string under `classData.installed_meter` using PascalCase:
   ```json
   {
     "classData": "{\"installed_meter\":{\"MeterId\":\"J100004\",\"SerialNo\":\"SE65293\",\"Make\":\"Genus\",\"PhaseType\":\"single\",\"InstallationStatus\":\"Faulty\",\"InstallationType\":\"CT Operated\"}}"
   }
   ```

* **Adapter Solution:** Our client layer abstracts away this divergence completely, normalizing both variants into a strictly-typed, unified `MeterDetail` schema.

---

## 6. The Bulk Extraction Path & HMAC-SHA256 Signing

In `nodes/4.2Bgc2kUI.js` (Transformers view), we discovered an export routine used to download the complete grid dataset.

### 6.1 Key Retrieval
```http
GET /portal/keys
Host: urja-ops.flockenergy.tech
Cookie: __Secure-better-auth.session_token=...
```
Returns:
```json
{"data": {"signingSecret": "I3dZPPf5CgTp7JyGNMI8i6z8LFR7TmSR"}}
```

### 6.2 Signature Calculation
```python
import hmac, hashlib, time

timestamp = str(int(time.time()))
canonical_string = f"GET\n/portal/export\npage=1\n{timestamp}"
signature = hmac.new(
    signing_secret.encode('utf-8'),
    canonical_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

### 6.3 Request Execution
```http
GET /portal/export?page=1 HTTP/1.1
Host: urja-ops.flockenergy.tech
Cookie: __Secure-better-auth.session_token=...
x-timestamp: 1729768621
x-signature: 4a2e5d...
```

### 6.4 Payload Characteristics
* Returns all **403 meters in a single HTTP transaction**.
* Each item includes pre-stitched `hierarchy` (`zone`, `circle`, `division`, `subdivision`, `substation`, `feeder`, `dt`) and `geo` (`lat`, `lng`).
* **Architectural Advantage:** Instead of performing 403 individual HTTP round-trips to scrape meters, our adapter leverages this bulk path for high-speed hydration of our in-memory query and indexing engine.
