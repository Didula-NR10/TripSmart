# Trip Smart — PlantUML Diagrams

Seven UML diagram types (use case, state, activity, ER, component, class, and two
sequence diagrams), reverse-engineered directly from the real codebase — not
invented — and syntax-validated with a local PlantUML render (`plantuml.jar`
v1.2024.7) before being included here. Every class name, method signature,
database column, endpoint path and status code below matches the actual
source: `Backend/core/models.py`, `Backend/auth/*`, `Backend/forecast/*`,
`Backend/reports/*`, `Backend/notes/*`, `Backend/main.py`, and the Frontend's
`app/`, `lib/api.ts`.

## How to render these

Any of the following work with the code blocks below, unmodified:

- **VS Code**: install the "PlantUML" extension (jebbs.plantuml), open this
  file, place the cursor inside a block and press `Alt+D` to preview.
- **Online**: paste a block into <https://www.plantuml.com/plantuml/uml/>.
- **CLI** (what was used to validate these): `java -jar plantuml.jar diagram.puml`
  produces a `.png` next to it. Requires only a JRE — get the jar from
  <https://github.com/plantuml/plantuml/releases>.
- **IntelliJ/PyCharm**: the "PlantUML integration" plugin renders `.puml`
  files or fenced blocks directly.

---

## 1. Use Case Diagram

Actors: an **Anonymous Tourist** can browse forecasts, laws, specialties and
ground reports, plus manage their own account, with no login. A **Registered
Traveller** *generalises* Anonymous Tourist (inherits everything above) and
additionally gets the actions that require a session — posting/deleting
reports, the notebook, the journal, notifications, and profile changes — all
routed through one shared `Authenticate Session` use case
(`auth.deps.get_current_user`, `<<include>>`d by every protected action).
`Resend OTP Code` `<<extend>>`s both Sign Up and Forgot Password, since it's
the same endpoint reused by two flows. External systems appear as secondary
actors on the use cases that actually call them.

```plantuml
@startuml TripSmart_UseCase
left to right direction
skinparam packageStyle rect

actor "Anonymous Tourist" as Anon
actor "Registered Traveller" as Trav
Trav --|> Anon

actor "Open-Meteo API" as OpenMeteo <<external>>
actor "Gmail SMTP" as SMTP <<external>>
actor "Cloudinary" as Cloudinary <<external>>
actor "OSM / Nominatim" as OSM <<external>>

rectangle "Trip Smart" {

  usecase "View 24h Forecast" as UC1
  usecase "View 7-day Outlook" as UC2
  usecase "View Current Conditions" as UC3
  usecase "Compare Two Districts" as UC4
  usecase "Search / Pick District on Map" as UC4b
  usecase "View District Laws & Advisories" as UC5
  usecase "View District Specialties" as UC6
  usecase "Browse Ground Reports" as UC7
  usecase "Receive District-Entry Notification" as UC8

  usecase "Sign Up" as UC9
  usecase "Verify Email (OTP)" as UC10
  usecase "Resend OTP Code" as UC24
  usecase "Log In" as UC11
  usecase "Log Out" as UC12
  usecase "Forgot Password" as UC13
  usecase "Reset Password" as UC14

  usecase "Authenticate Session" as UCAuth

  usecase "Change Password" as UC15
  usecase "Upload Profile Picture" as UC16
  usecase "Post Ground Report" as UC17
  usecase "Delete Own Ground Report" as UC18
  usecase "Write Travel Note" as UC19
  usecase "Delete Travel Note" as UC20
  usecase "Create Journal Book" as UC21
  usecase "Write Journal Page" as UC22
  usecase "Delete Journal Page" as UC23
}

Anon --> UC1
Anon --> UC2
Anon --> UC3
Anon --> UC4
Anon --> UC4b
Anon --> UC5
Anon --> UC6
Anon --> UC7
Anon --> UC9
Anon --> UC10
Anon --> UC24
Anon --> UC11
Anon --> UC13
Anon --> UC14

Trav --> UC8
Trav --> UC12
Trav --> UC15
Trav --> UC16
Trav --> UC17
Trav --> UC18
Trav --> UC19
Trav --> UC20
Trav --> UC21
Trav --> UC22
Trav --> UC23

UC15 ..> UCAuth : <<include>>
UC16 ..> UCAuth : <<include>>
UC17 ..> UCAuth : <<include>>
UC18 ..> UCAuth : <<include>>
UC19 ..> UCAuth : <<include>>
UC20 ..> UCAuth : <<include>>
UC21 ..> UCAuth : <<include>>
UC22 ..> UCAuth : <<include>>
UC23 ..> UCAuth : <<include>>
UC12 ..> UCAuth : <<include>>

UC24 ..> UC9 : <<extend>>
UC24 ..> UC13 : <<extend>>

UC1 -- OpenMeteo
UC2 -- OpenMeteo
UC3 -- OpenMeteo
UC4 -- OpenMeteo
UC4b -- OSM
UC9 -- SMTP
UC13 -- SMTP
UC15 -- SMTP
UC16 -- Cloudinary

@enduml
```

---

## 2. State Diagram

Three independent, fully-verified state machines: a **Ground Report**'s
lifecycle (`Backend/reports/repositories.py` — expiry is a hard `DELETE`
swept on every read/write, not a soft "expired" flag); an **Email OTP
Code**'s lifecycle (`Backend/auth/services.py::_check_otp` — attempts
counter, expiry, one-shot deletion on success); and the **User Session**
states that follow from `AuthService.login` / `verify_email` / `logout` /
`reset_password`.

```plantuml
@startuml TripSmart_State
hide empty description

state "Ground Report" as GR {
  [*] --> Active : create_report()\n(login required, district must exist)
  Active --> [*] : delete_report()\n(only the original author)
  Active --> [*] : auto-purge\n(created_at < now - 24h;\nswept on the next create/list/delete call)
}

state "Email OTP Code" as OTP {
  [*] --> Issued : signup() / forgot_password() /\nresend_otp() / change_password_request()\n(any previous code for the same\nemail+purpose is replaced)
  Issued --> Issued : verify: wrong code\n[attempts < OTP_MAX_ATTEMPTS] / attempts += 1
  Issued --> Verified : verify: correct code\n(before expiry, attempts < max)
  Issued --> Locked : verify: wrong code\n[attempts >= OTP_MAX_ATTEMPTS]
  Issued --> Expired : verify attempted\n[now() > expires_at]
  Verified --> [*] : row deleted
  Locked --> [*] : row deleted
  Expired --> [*] : row remains until\noverwritten by a fresh request
}

state "User Session" as Sess {
  [*] --> LoggedOut
  LoggedOut --> LoggedIn : login() correct credentials\n+ email_verified = true\n(creates AuthToken)
  LoggedOut --> LoggedIn : verify_email() correct OTP\n(auto-creates AuthToken)
  LoggedIn --> LoggedOut : logout()\n(deletes this AuthToken)
  LoggedIn --> LoggedOut : token expired\n(now() > expires_at, deleted on next use)
  LoggedIn --> LoggedOut : reset_password() on this account\n(ALL AuthTokens for the user deleted)
}

@enduml
```

---

## 3. Activity Diagram

The forecast pipeline, `ForecastService.forecast_district()` in
`Backend/forecast/services.py` plus the retry/backoff/stale-fallback logic in
`Backend/forecast/repositories.py::WeatherRepository`: cache check, model
readiness check, the Open-Meteo retry loop with exponential backoff, the
15-minute window cache, the stale-forecast fallback, feature engineering,
GRU inference, and persistence.

```plantuml
@startuml TripSmart_Activity
title Activity Diagram - GET /api/v1/forecast/{district}

start
:Client requests forecast for a district;
if (district in DISTRICT_COORDS?) then (no)
  :Return 404 Unknown district;
  stop
else (yes)
endif

if (refresh == false?) then (yes)
  :ForecastRepository.get_fresh(district);
  if (cached run found\n(< FORECAST_CACHE_MINUTES old)?) then (yes)
    :Mark payload cached = true;
    :Return cached ForecastResponse;
    stop
  else (no)
  endif
else (no)
endif

if (GRU model + scaler files on disk?) then (no)
  :Return 503 Service Unavailable;
  stop
else (yes)
endif

:attempt = 0, success = false;
while (attempt < OPEN_METEO_MAX_RETRIES\nand not success?) is (retry)
  :GET Open-Meteo /v1/forecast\n(past_days=7, forecast_days=1);
  if (HTTP 200?) then (yes)
    :success = true;
  else (no)
    if (status == 429 or status >= 500?) then (yes)
      :sleep(backoff seconds,\nhonour Retry-After header);
      :attempt += 1; backoff *= 2;
    else (no - e.g. 400)
      :raise RuntimeError\n(non-retryable);
      :Return 502 Bad Gateway;
      stop
    endif
  endif
endwhile (attempts exhausted\nor success)

if (success?) then (yes)
  :Cache the fresh 168h window\n(15-minute in-memory cache);
  :Build 168h DataFrame from response;
else (no)
  if (a previously cached window\nexists for this district?) then (yes)
    :Serve the stale cached window\n(log a warning);
  else (no)
    :Return 502 Bad Gateway;
    stop
  endif
endif

:ObservationRepository.save_window()\n(best-effort upsert into weather_observations);

:engineer_features(frame)\n(Hour_sin/cos, Month_sin/cos,\nTemp_Change_3h, DaylightScore, ...);
if (engineered features contain NaN?) then (yes)
  :Return 422 Unprocessable Entity;
  stop
else (no)
endif

:scaler.transform(features);
:GRU model.predict(168h tensor)\n-> (24, 3) scaled output;
:inverse_transform_targets();
:clamp_physical() per hour\n(temperature, rain, humidity);
:hourly_advisory() per hour\n(GOOD / CAUTION / AVOID + reason);
:daily_summary() across 24 hours;

:ForecastRepository.save(district, origin, payload)\n-> INSERT forecast_runs;

:Return ForecastResponse (cached = false);
stop

@enduml
```

---

## 4. Entity–Relationship (ER) Diagram

Every table in `Backend/core/models.py`, with exact column names/types and
the real foreign keys — including the two relationships that are
deliberately **not** enforced by a foreign key in the schema:
`ground_reports.author` is a plain username string resolved against `users`
only at read time (for the avatar lookup in `ReportRepository.list`), and
`email_otps` has no FK to `users` because a code can be issued for an email
before any verified account exists.

```plantuml
@startuml TripSmart_ER
hide circle
skinparam linetype ortho

entity "districts" as districts {
  * id : UUID <<PK>>
  --
  * name : text <<unique>>
  * lat : numeric(8,5)
  * lon : numeric(8,5)
  * created_at : timestamptz
}

entity "weather_observations" as obs {
  * id : UUID <<PK>>
  --
  * district_id : UUID <<FK>>
  * observed_at : timestamptz
  * temperature_c : numeric(5,2)
  * precipitation_mm : numeric(6,3)
  * humidity_pct : numeric(4,1)
  * cloud_cover_pct : numeric(4,1)
  * wind_speed_kmh : numeric(5,2)
  * wind_gusts_kmh : numeric(5,2)
  * daylight_score : numeric(5,4)
  * created_at : timestamptz
  --
  unique (district_id, observed_at)
}

entity "forecast_runs" as runs {
  * id : UUID <<PK>>
  --
  * district_id : UUID <<FK>>
  * forecast_origin : timestamptz
  * payload : jsonb
  * created_at : timestamptz
}

entity "ground_reports" as reports {
  * id : UUID <<PK>>
  --
  * district_id : UUID <<FK>>
  * location : text
  * title : text
  * body : text
  * author : text
  * created_at : timestamptz
}

entity "users" as users {
  * id : UUID <<PK>>
  --
  * full_name : text
  * username : text <<unique>>
  * email : text <<unique>>
  * country : text
  * password_hash : text
  * avatar_url : text
  * email_verified : boolean
  * created_at : timestamptz
  * updated_at : timestamptz
  last_login_at : timestamptz
}

entity "email_otps" as otps {
  * id : UUID <<PK>>
  --
  * email : text
  * code : text
  * purpose : text
  * attempts : integer
  * expires_at : timestamptz
  * created_at : timestamptz
}

entity "auth_tokens" as tokens {
  * token : text <<PK>>
  --
  * user_id : UUID <<FK>>
  * created_at : timestamptz
  * expires_at : timestamptz
}

entity "travel_journals" as journals {
  * id : UUID <<PK>>
  --
  * user_id : UUID <<FK>>
  * title : text
  * created_at : timestamptz
}

entity "travel_notes" as notes {
  * id : UUID <<PK>>
  --
  * user_id : UUID <<FK>>
  * place : text
  * body : text
  * photo_url : text
  journal_id : UUID <<FK, nullable>>
  page_number : integer <<nullable>>
  * created_at : timestamptz
  --
  unique (journal_id, page_number)
}

districts ||--o{ obs : "district_id"
districts ||--o{ runs : "district_id"
districts ||--o{ reports : "district_id"
users ||--o{ tokens : "user_id"
users ||--o{ journals : "user_id"
users ||--o{ notes : "user_id"
journals |o--o{ notes : "journal_id (optional page)"
reports }o..o{ users : "author = username\n(no FK constraint - resolved\nat read time for avatar lookup)"
otps .. users : "email (no FK - rows may\nprecede account creation)"

@enduml
```

---

## 5. Component Diagram

The full system boundary: the Expo/React Native client's five tabs plus the
journal screen, all going through one API client and auth context; the
FastAPI backend's four router modules sharing one `core` (config/DB/models)
layer; the GRU model artifact; and every external system actually integrated
(`Backend/core/config.py`, `Backend/auth/emailer.py`,
`Frontend/lib/cloudinary.ts`, the Leaflet/OSM map, and the Hugging Face
Spaces Docker host from `Backend/Dockerfile`).

```plantuml
@startuml TripSmart_Component
skinparam componentStyle rectangle

package "Mobile Client - Expo / React Native" {
  [Forecast Tab] as ForecastTab
  [Local Guide Tab] as CultureTab
  [Route Intelligence Tab] as RouterTab
  [Ground Reports Tab] as ReportsTab
  [Profile Tab] as ProfileTab
  [Travel Journal Screen] as JournalScreen
  [Leaflet / OpenStreetMap Map] as MapView
  [API Client (lib/api.ts)] as ApiClient
  [Auth Context (lib/auth.tsx)] as AuthCtx
  [Notification Service\n(lib/notify.ts, expo-notifications)] as NotifSvc
}

package "Trip Smart Backend - FastAPI" {
  [Auth Router + AuthService] as AuthMod
  [Forecast Router + ForecastService] as ForecastMod
  [Reports Router + ReportRepository] as ReportsMod
  [Notes / Journal Router] as NotesMod
  [Core: Config, Database, Models] as Core
  component "GRU Weather Model\n(best_checkpoint.keras + scaler.pkl)" as GRU
}

database "Supabase (PostgreSQL)" as DB
cloud "Open-Meteo API" as OpenMeteo
cloud "Gmail SMTP\n(aiosmtplib)" as SMTP
cloud "Cloudinary" as Cloudinary
cloud "OpenStreetMap / Nominatim" as OSM
node "Hugging Face Spaces\n(Docker, port 7860)" as HF

ForecastTab --> ApiClient
CultureTab --> ApiClient
RouterTab --> ApiClient
ReportsTab --> ApiClient
ProfileTab --> ApiClient
JournalScreen --> ApiClient
ForecastTab --> MapView
NotifSvc --> AuthCtx
ProfileTab --> AuthCtx
MapView --> OSM : search / reverse-geocode

ApiClient --> AuthMod : HTTPS/JSON\n/api/v1/auth/*
ApiClient --> ForecastMod : /api/v1/forecast/*
ApiClient --> ReportsMod : /api/v1/reports/*
ApiClient --> NotesMod : /api/v1/notes/*\n/api/v1/journals/*
ProfileTab --> Cloudinary : direct unsigned\nimage upload

AuthMod --> Core
ForecastMod --> Core
ReportsMod --> Core
NotesMod --> Core
Core --> DB : SQLAlchemy ORM

AuthMod --> SMTP : send OTP email
ForecastMod --> OpenMeteo : fetch observations
ForecastMod --> GRU : load model + predict()

HF ..> AuthMod : hosts
HF ..> ForecastMod : hosts
HF ..> ReportsMod : hosts
HF ..> NotesMod : hosts

@enduml
```

---

## 6. Class Diagram

The backend's actual classes across three packages, with real method
signatures: the SQLAlchemy ORM models (`core.models`), the forecast domain
(`ForecastService` and its four repositories from
`Backend/forecast/repositories.py` / `services.py`), `AuthService`
(`Backend/auth/services.py`), and `ReportRepository`
(`Backend/reports/repositories.py`).

```plantuml
@startuml TripSmart_Class
hide empty members
skinparam classAttributeIconSize 0

package "core.models (SQLAlchemy ORM)" {
  class District {
    +id : UUID {PK}
    +name : str {unique}
    +lat : Decimal
    +lon : Decimal
    +created_at : datetime
  }
  class WeatherObservation {
    +id : UUID {PK}
    +district_id : UUID {FK}
    +observed_at : datetime
    +temperature_c : Decimal
    +precipitation_mm : Decimal
    +humidity_pct : Decimal
    +cloud_cover_pct : Decimal
    +wind_speed_kmh : Decimal
    +wind_gusts_kmh : Decimal
    +daylight_score : Decimal
    +created_at : datetime
  }
  class ForecastRun {
    +id : UUID {PK}
    +district_id : UUID {FK}
    +forecast_origin : datetime
    +payload : JSONB
    +created_at : datetime
  }
  class GroundReport {
    +id : UUID {PK}
    +district_id : UUID {FK}
    +location : str
    +title : str
    +body : str
    +author : str
    +created_at : datetime
  }
  class User {
    +id : UUID {PK}
    +full_name : str
    +username : str {unique}
    +email : str {unique}
    +country : str
    +password_hash : str
    +avatar_url : str
    +email_verified : bool
    +created_at : datetime
    +updated_at : datetime
    +last_login_at : datetime
  }
  class EmailOtp {
    +id : UUID {PK}
    +email : str
    +code : str
    +purpose : str
    +attempts : int
    +expires_at : datetime
    +created_at : datetime
  }
  class AuthToken {
    +token : str {PK}
    +user_id : UUID {FK}
    +created_at : datetime
    +expires_at : datetime
  }
  class TravelJournal {
    +id : UUID {PK}
    +user_id : UUID {FK}
    +title : str
    +created_at : datetime
  }
  class TravelNote {
    +id : UUID {PK}
    +user_id : UUID {FK}
    +place : str
    +body : str
    +photo_url : str
    +journal_id : UUID {FK, nullable}
    +page_number : int {nullable}
    +created_at : datetime
  }

  District "1" -- "0..*" WeatherObservation
  District "1" -- "0..*" ForecastRun
  District "1" -- "0..*" GroundReport
  User "1" -- "0..*" AuthToken
  User "1" -- "0..*" TravelJournal
  User "1" -- "0..*" TravelNote
  TravelJournal "1" -- "0..10" TravelNote : pages
}

package "forecast" {
  class ForecastService {
    +list_districts() : List<DistrictInfo>
    +forecast_district(district, refresh) : dict
    +weekly_outlook(district) : dict
    +predict_from_records(district, records) : dict
    +current_conditions(district) : dict
    +history(district, limit) : List<dict>
    +health() : dict
    -_run_model(frame) : ndarray
    -_assemble(district, real, origin, last_obs_local, cached) : dict
  }
  class WeatherRepository {
    -_window_cache : dict
    +fetch_context_window(district) : DataFrame
    +fetch_current(district) : dict
    -_get_with_retry(params) : dict
    -_frame_from_hourly(hourly) : DataFrame
  }
  class ModelRepository <<static>> {
    +{static} get_model() : KerasModel
    +{static} get_scaler() : Scaler
    +{static} is_ready() : bool
  }
  class ForecastRepository {
    +get_fresh(district) : dict
    +get_stale(district) : dict
    +save(district, origin, payload) : void
    +history(district, limit) : List<dict>
  }
  class ObservationRepository {
    +save_window(district, frame) : void
  }
  class DistrictLookup <<static>> {
    +{static} id_for(district) : UUID
  }

  ForecastService o-- WeatherRepository
  ForecastService o-- ModelRepository
  ForecastService o-- ForecastRepository
  ForecastService o-- ObservationRepository
  ForecastRepository ..> DistrictLookup : uses
  ObservationRepository ..> DistrictLookup : uses
  ForecastRepository ..> ForecastRun : reads/writes
  ObservationRepository ..> WeatherObservation : upserts
  ModelRepository ..> District : (coords contract)
}

package "auth" {
  class AuthService {
    +signup(full_name, username, email, country, password) : dict
    +verify_email(email, otp) : dict
    +login(identifier, password) : dict
    +forgot_password(email) : dict
    +reset_password(email, otp, new_password) : dict
    +resend_otp(email, purpose) : dict
    +change_password_request(user) : dict
    +change_password_confirm(user, otp, new_password, current_token) : dict
    +set_avatar(user, avatar_url) : dict
    +logout(token) : dict
    +me(user) : dict
  }
  AuthService ..> User : creates / reads / updates
  AuthService ..> EmailOtp : issues / verifies
  AuthService ..> AuthToken : creates / revokes
}

package "reports" {
  class ReportRepository {
    +create(district, location, title, body, author) : dict
    +list(district, search) : List<dict>
    +delete(report_id, author) : bool
    -_purge_expired(session) : void
  }
  ReportRepository ..> GroundReport
  ReportRepository ..> District : resolves name to id
  ReportRepository ..> User : joins by username for avatar_url
}

@enduml
```

---

## 7. Sequence Diagram — Sign Up + Email OTP Verification

Covers `POST /api/v1/auth/signup` and `POST /api/v1/auth/verify-email`
exactly as implemented in `Backend/auth/routers.py` and
`Backend/auth/services.py`, including the conflict checks, the
development-mode `dev_otp` fallback when SMTP isn't configured, and every
branch of `_check_otp` (expired, locked, wrong code, correct code).

```plantuml
@startuml TripSmart_Sequence_Signup
actor Tourist
participant "Mobile App" as App
participant "AuthRouter" as Router
participant "AuthService" as Svc
database "Postgres\n(users, email_otps,\nauth_tokens)" as DB
participant "aiosmtplib\n(Gmail SMTP)" as SMTP

Tourist -> App : fill signup form\n(full name, username, email,\ncountry, password)
App -> Router : POST /api/v1/auth/signup
Router -> Svc : signup(full_name, username,\nemail, country, password)
Svc -> DB : SELECT User WHERE email = ? OR username = ?

alt account already verified with this email
  Svc --> Router : 409 Conflict
  Router --> App : error
else username taken by a different email
  Svc --> Router : 409 Conflict
else new signup or re-registering unverified account
  Svc -> DB : INSERT/UPDATE User\n(password_hash, email_verified=false)
  Svc -> DB : DELETE old EmailOtp(email, 'signup')
  Svc -> DB : INSERT EmailOtp\n(code, purpose='signup', expires_at)
  Svc -> SMTP : send_otp(email, code, 'signup')
  alt SMTP send succeeds
    SMTP --> Svc : sent
  else SMTP fails AND ENVIRONMENT=development
    Svc -> Svc : dev_otp = code (logged, returned in response)
  else SMTP fails in production
    Svc --> Router : 502 Bad Gateway
    Router --> App : error
  end
  Svc --> Router : {message, dev_otp?}
  Router --> App : 201 Created
end

App -> Tourist : show "enter the 6-digit code" screen
Tourist -> App : submit OTP code
App -> Router : POST /api/v1/auth/verify-email
Router -> Svc : verify_email(email, otp)
Svc -> DB : SELECT latest EmailOtp\nWHERE email, purpose='signup'

alt no code found, or now() > expires_at
  Svc --> Router : 400 Bad Request (expired/not found)
else attempts >= OTP_MAX_ATTEMPTS
  Svc -> DB : DELETE EmailOtp
  Svc --> Router : 400 Bad Request (too many attempts)
else code != submitted otp
  Svc -> DB : UPDATE EmailOtp SET attempts = attempts + 1
  Svc --> Router : 400 Bad Request (incorrect code)
else code matches
  Svc -> DB : DELETE EmailOtp
  Svc -> DB : UPDATE User SET email_verified = true,\nlast_login_at = now()
  Svc -> DB : INSERT AuthToken\n(token, user_id, expires_at = now()+SESSION_DAYS)
  Svc --> Router : {token, user}
  Router --> App : 200 OK
  App -> App : persist bearer token\n(sent as Authorization header\non every future request)
  App -> Tourist : navigate to app (logged in)
end

@enduml
```

---

## 8. Sequence Diagram — 24-Hour Forecast Request

Covers `GET /api/v1/forecast/{district}` end to end: the cache check, the
model-readiness guard, the Open-Meteo fetch with retry/backoff and the
15-minute window cache, the stale-forecast fallback, the GRU inference
steps, and the final cache write — matching
`ForecastService.forecast_district()` and
`WeatherRepository.fetch_context_window()` exactly.

```plantuml
@startuml TripSmart_Sequence_Forecast
actor Tourist
participant "Mobile App" as App
participant "ForecastRouter" as Router
participant "ForecastService" as Svc
participant "ForecastRepository" as Cache
participant "WeatherRepository" as Weather
participant "Open-Meteo API" as OM
participant "ModelRepository" as ModelRepo
participant "GRU Model" as GRU
database "Postgres" as DB

Tourist -> App : pick district, tap Predict
App -> Router : GET /api/v1/forecast/{district}?refresh=false
Router -> Svc : forecast_district(district, refresh=false)

Svc -> Cache : get_fresh(district)
Cache -> DB : SELECT ForecastRun\nWHERE district_id, forecast_origin >= now()-60min\nORDER BY forecast_origin DESC LIMIT 1

alt fresh cached run exists
  Cache --> Svc : cached payload
  Svc --> Router : payload (cached = true)
  Router --> App : 200 OK
else no fresh cache
  Svc -> ModelRepo : is_ready()
  ModelRepo --> Svc : true (model + scaler on disk)

  Svc -> Weather : fetch_context_window(district)
  Weather -> Weather : check 15-min in-memory\nwindow cache

  alt cached window still fresh
    Weather -> Weather : reuse cached hourly JSON
  else must fetch
    Weather -> OM : GET /v1/forecast\n(past_days=7, forecast_days=1)
    alt HTTP 200
      OM --> Weather : hourly observations JSON
    else HTTP 429 / 5xx
      loop up to OPEN_METEO_MAX_RETRIES
        Weather -> Weather : sleep(backoff, honour Retry-After)
        Weather -> OM : retry GET /v1/forecast
      end
      alt still failing and a stale window is cached
        Weather -> Weather : serve stale window (logged)
      else still failing, nothing cached
        Weather --> Svc : raise RuntimeError
        Svc --> Router : 502 Bad Gateway
        Router --> App : error
      end
    end
  end
  Weather --> Svc : 168h DataFrame

  Svc -> DB : ObservationRepository.save_window()\n(best-effort upsert, errors swallowed)

  Svc -> Svc : engineer_features(frame)
  Svc -> ModelRepo : get_scaler()
  ModelRepo --> Svc : fitted MinMaxScaler
  Svc -> Svc : scaler.transform(features)
  Svc -> ModelRepo : get_model()
  ModelRepo --> Svc : loaded Keras GRU model
  Svc -> GRU : predict(168h tensor)
  GRU --> Svc : (24, 3) scaled predictions

  Svc -> Svc : inverse_transform_targets()
  Svc -> Svc : clamp_physical() per hour
  Svc -> Svc : hourly_advisory() per hour\n(GOOD / CAUTION / AVOID)
  Svc -> Svc : daily_summary()

  Svc -> Cache : save(district, origin, payload)
  Cache -> DB : INSERT ForecastRun

  Svc --> Router : ForecastResponse (cached = false)
  Router --> App : 200 OK
end

App -> Tourist : render hourly forecast + advisories

@enduml
```
