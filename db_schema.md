# Database Schema — Travellino

## Apps Structure

```
users/      — authentication and user profile
catalog/    — reference data (cities, activities, transport, accommodation)
trips/      — trip entities and bookings
```

---

## App: users

### CustomUser
Auth model. Extends Django `AbstractUser`. Used by Django auth system, JWT, `request.user`.

| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | auto primary key |
| email | EmailField | unique, used as login |
| phone | CharField | unique, format +380XXXXXXXXX |
| first_name | CharField | required |
| last_name | CharField | required |
| username | CharField | nullable, not used |
| is_active | BooleanField | default False, set to True after email verification |
| is_email_verified | BooleanField | default False |
| is_staff | BooleanField | default False |
| is_superuser | BooleanField | default False |

> `USERNAME_FIELD = 'email'` — login is done by email, not username.
> User is inactive until email is verified.

---

### UserProfile
Separate table for non-auth user data. Created separately from CustomUser.

| Field | Type | Notes |
|---|---|---|
| user | OneToOneField → CustomUser | primary key, cascade delete |
| photo | URLField | nullable, link to object storage |
| preferences | ArrayField(CharField) | array of preference tags |

> **TODO:** `preferences` currently accepts any string. After finalizing the tag list — add `TextChoices` enum and `choices` validation, then migrate.

---

## App: catalog

Reference data. Not user-specific. Populated from dataset, not via API.

### City

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| city | CharField | city name |
| country | CharField | |
| region | CharField | |
| short_description | TextField | |
| ideal_durations | ArrayField(CharField) | array of duration tags |
| budget_level | CharField | choices: Budget, Mid-range, Luxury |
| culture | DecimalField(3,1) | rating 0—5 |
| nature | DecimalField(3,1) | rating 0—5 |
| beaches | DecimalField(3,1) | rating 0—5 |
| nightlife | DecimalField(3,1) | rating 0—5 |
| cuisine | DecimalField(3,1) | rating 0—5 |

> **TODO:** `BudgetLevel` and `IdealDuration` enums contain temporary values for testing.
> Extract unique values from dataset and update before production.

> **Reserve fields (commented out, not in DB):**
> - `latitude`, `longitude` — for future transport/accommodation API integration
> - `avg_temp_monthly` — JSONField, monthly temperatures, for city detail page

---

### Activity
Reference catalog of places and activities per city.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| city | ForeignKey → City | cascade delete |
| title | CharField | |
| description | TextField | |
| category | CharField | choices: Culture, Nature, Beaches, Nightlife, Cuisine |

> **TODO:** `ActivityCategory` enum contains temporary values.
> Finalize category list and migrate.

---

### TransportOption
Reference transport routes. Used for testing and as cache for external API results.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| departure_point | CharField | |
| arrival_point | CharField | |
| transport_type | CharField | choices: Flight, Train, Bus |
| carrier_name | CharField | e.g. Ryanair |
| route_number | CharField | flight or train number |
| base_price | DecimalField(10,2) | price per person |

> **TODO:** `TransportType` enum — verify all required values against dataset.

---

### AccommodationOption
Reference hotels and accommodations. Used for testing and as cache for external API results.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| city | ForeignKey → City | cascade delete |
| name | CharField | |
| address | CharField | |
| rating | DecimalField(3,1) | |
| description | TextField | |
| price_per_night | DecimalField(10,2) | |

---

## App: trips

Business entities. User-specific.

### Trip

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| title | CharField | filled manually or auto-generated from city name |
| city | ForeignKey → City | PROTECT — city cannot be deleted while trips exist |
| start_date | DateField | |
| end_date | DateField | |
| owner | ForeignKey → CustomUser | cascade delete |

---

### TransportBooking
Saved transport option within a trip.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| trip | ForeignKey → Trip | cascade delete |
| departure_point | CharField | |
| arrival_point | CharField | |
| departure_datetime | DateTimeField | |
| arrival_datetime | DateTimeField | |
| price | DecimalField(10,2) | fixed price at time of booking |
| passengers_count | PositiveIntegerField | |
| transport_option | ForeignKey → TransportOption | nullable, SET_NULL — for test data |
| transport_details_id | CharField | nullable, external API id — for production |

> Two separate fields for two separate workflows:
> `transport_option` — used when testing with reference data.
> `transport_details_id` — used when working with external transport API.
> Both are optional. Only one is expected to be filled at a time.

---

### AccommodationBooking
Saved accommodation option within a trip.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| trip | ForeignKey → Trip | cascade delete |
| accommodation_name | CharField | name from API response |
| check_in_date | DateField | |
| check_out_date | DateField | |
| price_per_night | DecimalField(10,2) | |
| total_price | DecimalField(10,2) | fixed total at time of booking |
| accommodation_option | ForeignKey → AccommodationOption | nullable, SET_NULL — for test data |
| accommodation_details_id | CharField | nullable, external API id — for production |

> Same dual-field pattern as TransportBooking.

---

### TripActivity
Scheduled activity within a trip. Used for calendar planning and .ics export.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| trip | ForeignKey → Trip | cascade delete |
| activity | ForeignKey → Activity | nullable, SET_NULL — for test data |
| activity_details_id | CharField | nullable, external API id — for production |
| scheduled_date | DateField | specific date within trip |
| start_time | TimeField | required for calendar grid |
| end_time | TimeField | |

---

### TripParticipant
Tracks invitations and access rights for shared trips.

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | primary key |
| trip | ForeignKey → Trip | cascade delete |
| user | ForeignKey → CustomUser | nullable, SET_NULL — user may not be registered yet |
| invitee_email | EmailField | email the invitation was sent to |
| access_level | CharField | choices: View, Edit |
| status | CharField | choices: Pending, Accepted — default Pending |

> `user` is nullable because invitation can be sent to an email that is not yet registered.
> After registration the user is linked to the existing TripParticipant record.

---

## General Notes

- All custom model primary keys are `UUIDField`. `CustomUser` uses default Django `BigAutoField`.
- `ArrayField` is PostgreSQL-specific. Requires `django.contrib.postgres` in `INSTALLED_APPS`.
- All enums marked **TODO** contain temporary values and must be updated before production data load.
- Reserved fields in `City` are commented out in code and not present in DB. Uncomment and migrate when needed.
- No service layer or endpoints are implemented yet. Data layer only.
