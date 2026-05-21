# 01 - Signal Variables Dictionary

## Purpose

This file defines the master signal vocabulary for the personal AI ecosystem.

It is not a final database schema. It is the dictionary that future schemas, API payloads, n8n workflows, model prompts, pgvector memories, and app state contracts must align with.

Use `TODO` where the existing documentation does not define a concrete value, provider, or threshold.

## Conventions

Reliability levels:
- `user_confirmed`: explicitly validated by the user
- `system_calculated`: deterministic system output
- `device_reported`: GPS, device, wearable, OS, or capture signal
- `external_feed`: third-party data source
- `ai_inferred`: model output that should be explainable
- `mixed`: combination of several sources
- `TODO`: not defined yet

Privacy levels:
- `low`: non-sensitive UI or configuration
- `medium`: useful personal context
- `high`: financial, location, health, religious, or behavioral data
- `very_high`: raw screenshots, audio, documents, religious privacy, precise location, or sensitive financial detail

Storage values:
- `yes`: store canonical value
- `no`: do not store
- `summary_only`: store a semantic summary, not raw sensitive data
- `conditional`: store only when useful and permitted by workflow
- `TODO`: decision missing

## Global User Context

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| user_id | global_user_context | Core | uuid/string | `single_user` | all apps, backend, n8n | backend | fixed | system_calculated | high | yes | yes | no | Technical identifier even though product is one-user only. |
| single_user_mode | global_user_context | Core | boolean | `true` | all apps, backend | backend | fixed | system_calculated | low | yes | yes | no | Product rule: not SaaS. |
| user_priority_order | global_user_context | Imperium | array | `["Religion","Discipline","Family","Money","Health","Project"]` | Imperium, n8n, AI router, all app planners | user via Imperium | on change | user_confirmed | high | yes | yes | summary_only | Order is the priority. |
| ai_strictness_mode | global_user_context | Imperium | enum | `strict` | Imperium, n8n, AI router | user via Settings & IA | on change | user_confirmed | medium | yes | yes | summary_only | Exact enum values TODO. |
| planning_confidence_level | global_user_context | Core | enum/number | `reduced` | Imperium, n8n, AI advice | backend, weekly review workflow | after review/anomaly | mixed | medium | yes | yes | summary_only | Drops when weekly review is overdue or data is missing. |
| system_language | global_user_context | Core | enum | `fr-FR` | apps, AI prompts | user/backend | TODO | TODO | low | no | TODO | no | Not defined in source docs. |
| notification_preferences | global_user_context | Imperium | object | `{"weekly_review":true}` | backend, push, n8n | user via Settings | on change | user_confirmed | medium | yes | yes | no | Specific fields TODO. |
| permission_profile | global_user_context | Core | object | `{"gps":true,"screen_capture":true}` | apps, backend | device/user | on permission change | device_reported | high | yes | yes | no | Used to decide fallback behavior. |

## Time Context

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current_datetime | time_context | Core | timestamp | `2026-04-25T09:15:00+02:00` | all workflows | backend/device | per request | system_calculated | low | yes | conditional | no | Request-local clock value. |
| timezone | time_context | Core | string | `Europe/Paris` | all workflows | device/user | on change | device_reported | medium | yes | yes | no | Needed for prayers, missions, daily cycles. |
| day_session_id | time_context | Imperium | uuid | `ds_20260425` | Imperium, n8n, mission engine | Imperium/backend | day start | system_calculated | medium | yes | yes | no | One active day session max. |
| day_session_status | time_context | Imperium | enum | `active` | Imperium, n8n | Imperium/backend | start/end | user_confirmed | medium | yes | yes | no | `active`, `completed`. |
| day_started_at | time_context | Imperium | timestamp | `2026-04-25T08:00:00+02:00` | Imperium, n8n | Imperium/backend | day start | user_confirmed | medium | yes | yes | no | Manual start. |
| day_ended_at | time_context | Imperium | timestamp nullable | `null` | Imperium, n8n | Imperium/backend | day end | user_confirmed | medium | yes | yes | no | Manual end. |
| day_elapsed_seconds | time_context | Imperium | integer | `17420` | Imperium UI, n8n | backend/UI | live | system_calculated | low | yes | conditional | no | May be computed, not stored every tick. |
| current_period_start | time_context | The Vault | date | `2026-04-01` | Vault, Imperium, AI objective | backend/user | period change | TODO | high | yes | yes | no | Period definition TODO. |
| current_period_end | time_context | The Vault | date | `2026-04-30` | Vault, Imperium, AI objective | backend/user | period change | TODO | high | yes | yes | no | Period definition TODO. |
| days_remaining_in_period | time_context | The Vault | integer | `6` | Vault, Imperium, AI objective | backend | daily | system_calculated | medium | yes | conditional | no | Used by daily minimum formula. |
| weekly_review_due_date | time_context | Imperium | date | `2026-04-28` | Imperium, n8n | backend | weekly | system_calculated | medium | yes | yes | no | Preferred schedule: Tuesday morning. |
| weekly_review_overdue | time_context | Imperium | boolean | `false` | Imperium, AI router | backend | daily | system_calculated | medium | yes | yes | summary_only | Reduces planning confidence if true. |
| prayer_time_window | time_context | The Path | object | `{"asr":"18:12"}` | Imperium, Path, Pulse | Path/backend | daily/location change | mixed | high | yes | yes | no | Use mosque times first if available. |
| fasting_window | time_context | The Path | object | `{"suhoor":"04:35","iftar":"21:04"}` | Pulse, Imperium, Path | Path/backend | daily | mixed | high | yes | yes | summary_only | Active only on fasting days. |

## Location Context

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| latitude | location_context | Device/Core | decimal nullable | `48.8566` | Vault, Vector, Pulse, Path, n8n | device/user | on capture | device_reported | very_high | yes | conditional | no | Store when tied to explicit event. |
| longitude | location_context | Device/Core | decimal nullable | `2.3522` | Vault, Vector, Pulse, Path, n8n | device/user | on capture | device_reported | very_high | yes | conditional | no | Store when tied to explicit event. |
| location_text | location_context | Device/Core | string | `Station Total - Paris` | Vault, Vector, Pulse, Path, Imperium | device, user, AI extraction | on capture/edit | mixed | high | yes | yes | summary_only | User can edit. |
| location_source | location_context | Device/Core | enum | `gps` | all location consumers | device/user/AI | on capture/edit | mixed | high | yes | yes | no | Allowed source values: `gps`, `manual`, `ai_extracted`, `unknown`. |
| current_zone | location_context | Vector | string | `Paris 13` | Vector, Imperium | Vector/backend | during VTC session | mixed | high | yes | conditional | summary_only | Exact zone taxonomy TODO. |
| last_known_area | location_context | Core | string nullable | `Stains` | all apps | device/backend | location capture | device_reported | high | conditional | conditional | summary_only | Fallback behavior requires product approval. |
| route_type | location_context | Vector | enum | `airport_route` | Vector | Vector/backend | route analysis | mixed | medium | yes | yes | summary_only | Used for learned ETA multiplier. |
| nearby_mosque_id | location_context | The Path | string nullable | `mawaqit_123` | Path, Imperium | Path/external feed | location/prayer refresh | external_feed | high | yes | yes | no | Exact provider mapping TODO. |
| recommended_mosque_gps | location_context | The Path | object nullable | `{"lat":48.86,"lng":2.35}` | Path, Imperium | Path/backend | prayer refresh | mixed | high | yes | conditional | no | Best realistic prayer option, not nearest only. |
| nearby_fuel_station_options | location_context | Vector | array | `[{"name":"TODO","eta_min":6}]` | Vector | external feed/backend | fuel trigger | external_feed | medium | yes | conditional | no | Provider TODO. |
| nearby_park_or_equipment | location_context | Pulse | array | `["park","pull_up_bar"]` | Pulse | Pulse/Vector/device | workout planning | mixed | medium | yes | conditional | summary_only | Exact source TODO. |

## Device Context

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| device_id | device_context | Core | string | `phone_primary` | backend, auth, app logs | app/device | install/session | TODO | high | conditional | yes | no | Exact identity model TODO. |
| source_app | device_context | Client apps | enum | `Vector` | backend, n8n, AI router | app | per request | system_calculated | low | yes | yes | no | Required routing field. |
| app_version | device_context | Client apps | string | `TODO` | backend, diagnostics | app | per request | device_reported | low | conditional | yes | no | Not defined in source docs. |
| platform | device_context | Client apps | enum | `android` | backend, diagnostics | app | per request | device_reported | low | conditional | yes | no | Exact target platform TODO. |
| gps_permission_status | device_context | Device | enum | `granted` | Vault, Vector, Pulse, Path | device/app | permission change | device_reported | high | yes | yes | no | Affects location fallback. |
| screen_capture_permission_status | device_context | Device/Vector | enum | `granted` | Vector | device/app | permission change | device_reported | very_high | yes | yes | no | Needed for ride screenshot extraction. |
| audio_capture_permission_status | device_context | Device/Core | enum | `granted` | AI router, Vector, transcription | device/app | permission change | device_reported | very_high | yes | yes | no | Needed for audio transcription or ride sound trigger. |
| notification_permission_status | device_context | Device/Core | enum | `granted` | push, n8n, apps | device/app | permission change | device_reported | medium | yes | yes | no | Used for reminders and signal pushes. |
| offline_mode | device_context | Device/Core | boolean | `false` | AI router, apps | app/device | per request | device_reported | medium | yes | conditional | no | Routes to local-only when true. |
| battery_state | device_context | Device/Core | object | `{"level":42,"charging":false}` | Vector, Pulse, backend | device | per request/session | device_reported | medium | conditional | conditional | no | Not defined in source docs; use only if needed. |
| wearable_connected | device_context | Pulse | boolean | `true` | Pulse, AI router | Pulse/device | on sync | device_reported | high | yes | yes | no | System must work without wearable. |

## Imperium Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current_mission_id | Imperium | Imperium | uuid nullable | `mis_123` | Imperium, widget, n8n, all app sync | Imperium/backend | mission change | system_calculated | high | yes | yes | summary_only | Only one current mission can exist. |
| mission_title | Imperium | Imperium | string | `Call insurance company` | Imperium, widget, AI advice | system/user | mission create/update | mixed | high | yes | yes | summary_only | Mission is operational. |
| mission_type | Imperium | Imperium | enum | `VTC work` | Imperium, n8n, AI router | system/user | mission create/update | mixed | medium | yes | yes | summary_only | Categories include VTC, sport, prayer, Quran, family, sleep, project action. |
| mission_target | Imperium | Imperium | string nullable | `250 EUR CA` | Imperium, Vector, Vault | system/user | mission create/update | mixed | high | yes | yes | summary_only | Optional. |
| mission_estimated_duration | Imperium | Imperium | integer nullable | `45` | Imperium, Pulse, Vector | system/AI | mission create/update | ai_inferred | medium | yes | yes | summary_only | Minutes. |
| mission_scheduled_start | Imperium | Imperium | timestamp nullable | `2026-04-25T10:00:00+02:00` | Imperium, Path, Pulse, Vector | system/AI | mission create/update | mixed | medium | yes | yes | no | Optional. |
| mission_scheduled_end | Imperium | Imperium | timestamp nullable | `2026-04-25T10:45:00+02:00` | Imperium, Path, Pulse, Vector | system/AI | mission create/update | mixed | medium | yes | yes | no | Optional. |
| mission_source_type | Imperium | Imperium | enum | `routine_generated` | Imperium, n8n | backend | mission create | system_calculated | medium | yes | yes | no | `system_generated`, `routine_generated`, `project_generated`, `manual_override`. |
| mission_status | Imperium | Imperium | enum | `current` | Imperium, n8n, apps | user/backend | mission event | user_confirmed | high | yes | yes | summary_only | `planned`, `current`, `done`, `not_done`, `cancelled`. |
| mission_failure_reason_category | Imperium | Imperium | enum | `fatigue` | Imperium, n8n, learning | user | mission failure | user_confirmed | high | yes | yes | summary_only | Categories TODO beyond replanning examples. |
| mission_failure_reason_detail | Imperium | Imperium | text nullable | `Too tired after VTC session` | Imperium, n8n, learning | user | mission failure | user_confirmed | high | yes | yes | summary_only | Failure is learning signal. |
| replan_reason_category | Imperium | Imperium | enum | `new_event` | Imperium, n8n, AI router | user/system | replanning | user_confirmed | high | yes | yes | summary_only | Suggested: `new_event`, `wrong_estimation`, `fatigue`, `priority_shift`, `other`. |
| replan_reason_detail | Imperium | Imperium | text nullable | `Unexpected family obligation` | Imperium, n8n, AI router | user | replanning | user_confirmed | high | yes | yes | summary_only | Traceable context. |
| previous_plan_snapshot | Imperium | Imperium | json nullable | `{...}` | n8n, audit, learning | backend | replanning | system_calculated | high | yes | yes | no | Optional. |
| new_plan_snapshot | Imperium | Imperium | json nullable | `{...}` | Imperium, n8n, learning | backend/AI | replanning | mixed | high | yes | yes | summary_only | Optional. |
| project_id | Imperium | Imperium | uuid | `proj_123` | Imperium, n8n, AI planner | user/system | project changes | user_confirmed | high | yes | yes | summary_only | Projects are strategic. |
| project_title | Imperium | Imperium | string | `Buy VTC vehicle` | Imperium, AI planner | user | project changes | user_confirmed | high | yes | yes | summary_only | Can generate missions. |
| project_priority_order | Imperium | Imperium | integer | `1` | Imperium, AI planner | user/AI suggestion after validation | on reorder | user_confirmed | high | yes | yes | summary_only | First active project is top priority. |
| project_status | Imperium | Imperium | enum | `active` | Imperium, AI planner | user | project changes | user_confirmed | high | yes | yes | summary_only | `active`, `paused`, `future`, `completed`; abandoned later if needed. |
| project_progress_percent | Imperium | Imperium | integer | `45` | Imperium, Hall of Fame, AI | user/system | project changes | mixed | medium | yes | yes | summary_only | Exact computation TODO. |
| project_completed_at | Imperium | Imperium | timestamp nullable | `2026-04-25T12:00:00+02:00` | Imperium, Hall of Fame, learning | user/backend | explicit validation | user_confirmed | high | yes | yes | summary_only | Never purely automatic. |
| project_completion_method | Imperium | Imperium | enum | `manual` | Imperium, learning | user/backend | explicit validation | user_confirmed | medium | yes | yes | no | `suggested`, `manual`. |
| routine_id | Imperium | Imperium | uuid | `routine_quran` | Imperium, n8n | user | routine changes | user_confirmed | medium | yes | yes | summary_only | Routines managed in Operations. |
| routine_title | Imperium | Imperium | string | `Quran` | Imperium, Path, n8n | user/system | routine changes | user_confirmed | high | yes | yes | summary_only | Routine can generate mission. |
| routine_estimated_daily_duration | Imperium | Imperium | integer | `20` | Imperium, AI planner | user/system | routine changes | mixed | medium | yes | yes | summary_only | Minutes. |
| weekly_review_id | Imperium | Imperium | uuid | `wr_2026w18` | Imperium, n8n, all planners | backend | weekly | system_calculated | high | yes | yes | summary_only | Strategic calibration event. |
| weekly_review_status | Imperium | Imperium | enum | `pending` | Imperium, n8n | backend/user | weekly/review completion | mixed | high | yes | yes | summary_only | `pending`, `completed`. |
| weekly_review_answer | Imperium | Imperium | object | `{"section":"Finance","answer":"new expense"}` | n8n, all planners, learning | user | during review | user_confirmed | very_high | yes | yes | summary_only | Related table required. |
| detected_changes_count | Imperium | Imperium | integer | `3` | Imperium, n8n, planners | backend/AI | review completion | mixed | high | yes | yes | summary_only | From weekly review. |
| ai_short_advice | Imperium | Imperium/Core | string | `Priority active: VTC work` | Imperium dashboard | AI/n8n | context change | ai_inferred | medium | yes | conditional | summary_only | Max 2 lines. |
| ai_detailed_advice | Imperium | Imperium/Core | text | `Financial pressure is high because...` | Imperium popup | AI/n8n | on demand/context change | ai_inferred | high | yes | conditional | summary_only | No fluff. |
| feed_ia_document_id | Imperium | Imperium | uuid | `doc_123` | n8n, memory, AI router | backend | upload | system_calculated | very_high | yes | yes | yes | Document metadata in PostgreSQL; chunks in pgvector. |
| feed_ia_upload_status | Imperium | Imperium | enum | `processing` | Imperium, n8n | backend | upload pipeline | system_calculated | high | yes | yes | no | `uploading`, `processing`, `completed`, `error`. |
| energy_score | Imperium | Imperium/Pulse | integer nullable | `72` | Imperium, Pulse, AI planner | TODO | TODO | TODO | high | yes | yes | summary_only | Scoring model postponed in source docs. |
| discipline_score | Imperium | Imperium/Core | integer nullable | `81` | Imperium, Path, Pulse, AI planner | backend/AI | daily/weekly | mixed | high | yes | yes | summary_only | Exact scoring model postponed. |

## Vector Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vtc_session_id | Vector | Vector | uuid | `vs_123` | Vector, Imperium, Vault, learning | Vector/backend | session start/end | user_confirmed | high | yes | yes | summary_only | Session result feeds learning. |
| vtc_target_ca | Vector | Imperium/Vector | decimal | `250.00` | Vector, Imperium, Vault | Imperium/backend | mission/session | mixed | high | yes | yes | summary_only | Revenue reference for a VTC session, not a global pressure signal. |
| vtc_final_ca | Vector | Vector/The Vault | decimal | `284.50` | Vector, Vault, Imperium | user/Vector/Vault | session end/transaction | user_confirmed | high | yes | yes | summary_only | Final revenue. |
| vtc_objective_reached | Vector | Vector | boolean | `true` | Vector, Imperium, learning | backend | session end | system_calculated | medium | yes | yes | summary_only | Compared with VTC session revenue reference when available. |
| ride_offer_id | Vector | Vector | uuid | `ride_123` | Vector, n8n, learning | backend | ride detection | system_calculated | high | yes | yes | no | Derived from screenshot/capture. |
| ride_offer_price | Vector | Vector | decimal | `38.00` | Vector decision engine | Gemini/OCR/user | ride detection | mixed | high | yes | yes | no | Extracted from Bolt offer or entered manually. |
| pickup_distance | Vector | Vector | decimal | `2.4` | Vector decision engine | Gemini/OCR/maps | ride detection | mixed | high | yes | yes | no | Unit TODO. |
| total_estimated_time | Vector | Vector | integer | `42` | Vector decision engine | Gemini/OCR/maps/backend | ride detection | mixed | high | yes | yes | summary_only | Minutes, adjusted by learned multiplier if possible. |
| destination_zone | Vector | Vector | string | `Orly` | Vector, Imperium | Gemini/OCR/maps/user | ride detection | mixed | high | yes | yes | summary_only | Zone taxonomy TODO. |
| return_probability | Vector | Vector | number | `0.72` | Vector decision engine | AI/rules | ride analysis | ai_inferred | high | yes | yes | summary_only | Must be explainable. |
| hourly_rate_estimate | Vector | Vector | decimal | `54.20` | Vector, Imperium | backend/rules | ride analysis | system_calculated | high | yes | yes | summary_only | Top evaluation priority. |
| strategic_direction | Vector | Vector/Imperium | string | `return Paris` | Vector, Imperium | Imperium/AI/rules | session context | mixed | high | yes | yes | summary_only | Depends on active mission and strategy. |
| airport_value | Vector | Vector | number | `0.64` | Vector decision engine | rules/AI/external feeds | ride analysis | mixed | medium | yes | yes | summary_only | Uses demand window, not landing time only. |
| event_value | Vector | Vector | number | `0.41` | Vector decision engine | external feeds/rules | ride analysis | mixed | medium | yes | yes | summary_only | Events/concerts source TODO. |
| scheduled_ride_nearby | Vector | Vector | boolean | `true` | Vector decision engine | Vector/backend | session | system_calculated | medium | yes | yes | no | Protects guaranteed revenue floor. |
| scheduled_ride_value | Vector | Vector | decimal | `42.00` | Vector decision engine | user/backend | scheduled ride create/update | user_confirmed | high | yes | yes | summary_only | Planned ride value. |
| destination_mode_remaining | Vector | Vector | integer | `4` | Vector decision engine | Vector/backend | daily/usage | system_calculated | medium | yes | yes | no | Max 6/day. |
| destination_mode_use_case | Vector | Vector | enum | `return_paris` | Vector | AI/user/rules | recommendation | mixed | medium | yes | yes | summary_only | Use cases include airport, home, event, strong zone, or return-to-Paris. |
| fuel_autonomy_km | Vector | Vector | integer | `180` | Vector, Imperium | user/device/TODO | fuel trigger | user_confirmed | high | yes | yes | summary_only | Low fuel trigger example: < 200 km. Exact threshold TODO. |
| fuel_low_triggered | Vector | Vector | boolean | `true` | Vector, n8n | user | button press | user_confirmed | high | yes | yes | summary_only | Does not mean refuel now; means plan intelligent refuel. |
| google_eta_minutes | Vector | External/Vector | integer | `10` | Vector | maps provider | per route | external_feed | medium | yes | yes | no | Provider TODO. |
| real_duration_minutes | Vector | Vector | integer | `14` | Vector learning | user/device | after route/session | mixed | high | yes | yes | summary_only | Used to learn ETA multiplier. |
| learned_eta_multiplier | Vector | Vector | decimal | `1.35` | Vector decision engine | backend/learning | after enough observations | system_calculated | medium | yes | yes | summary_only | Dynamic, not hardcoded. |
| ride_decision | Vector | Vector | enum | `ACCEPT` | Vector UI, learning | rules/AI | ride analysis | mixed | high | yes | yes | summary_only | Recommendation only. User decides. |
| recommendation_halo_state | Vector | Vector | enum | `green` | Vector overlay | backend/AI | ride analysis | system_calculated | medium | yes | conditional | no | `white`, `green`, `red`. |
| no_auto_click_enforced | Vector | Vector | boolean | `true` | Vector, compliance checks | backend/app | fixed | system_calculated | low | yes | yes | no | Critical platform boundary. |
| ride_user_action | Vector | Vector | enum | `accepted` | Vector, learning | user | after offer | user_confirmed | high | yes | yes | summary_only | Accepted/refused/missed TODO. |
| bad_recommendation_flag | Vector | Vector/Imperium | boolean | `true` | Vector, learning, weekly review | user | feedback/review | user_confirmed | high | yes | yes | summary_only | Critical learning data. |

## The Vault Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| transaction_id | The Vault | The Vault | uuid | `txn_123` | Vault, Imperium, learning | backend | transaction create | system_calculated | high | yes | yes | no | Canonical financial event. |
| transaction_type | The Vault | The Vault | enum | `expense` | Vault, Imperium, AI objective | user/OCR | transaction create/update | user_confirmed | high | yes | yes | summary_only | `gain` or `expense`. |
| transaction_category | The Vault | The Vault | string | `carburant` | Vault, AI objective, Pulse | user/OCR | transaction create/update | mixed | high | yes | yes | summary_only | For gains, this may represent origin. |
| transaction_amount | The Vault | The Vault | decimal | `52.40` | Vault, Imperium, AI objective, Path | user/OCR | transaction create/update | mixed | very_high | yes | yes | summary_only | Amount must be > 0. |
| wallet_type | The Vault | The Vault | enum | `CB` | Vault, AI objective | user | transaction create/update | user_confirmed | high | yes | yes | no | Fixed V1 values: `CB`, `Cash`, `Crypto`. |
| transaction_date | The Vault | The Vault | date | `2026-04-25` | Vault, AI objective | user/default | transaction create/update | mixed | high | yes | yes | no | Auto-filled, visible, editable. |
| transaction_time | The Vault | The Vault | time | `14:05` | Vault, AI objective | user/default | transaction create/update | mixed | high | yes | yes | no | Auto-filled, visible, editable. |
| transaction_source_type | The Vault | The Vault | enum | `scan_ticket` | Vault, AI router | app/OCR/user | transaction create | mixed | high | yes | yes | no | `manual`, `scan_ticket`, `imported_image`, `system_generated`. |
| transaction_notes | The Vault | The Vault | text nullable | `Fuel before airport` | Vault, AI memory | user | transaction create/update | user_confirmed | high | conditional | yes | summary_only | Optional. |
| ai_confidence | The Vault | AI routing | decimal nullable | `0.86` | Vault, AI router | AI/OCR | OCR/import | ai_inferred | medium | yes | yes | no | For extracted transaction fields. |
| raw_extracted_text | The Vault | Gemini/OCR | text nullable | `TOTAL 52.40 EUR` | Vault, audit | OCR | scan/import | ai_inferred | very_high | conditional | conditional | no | Raw sensitive data; retention TODO. |
| derived_wallet_available_balance | The Vault | The Vault | decimal | `500.00` | Vault, Imperium, AI objective | backend | query/calculation | system_calculated | very_high | yes | no | summary_only | Derived display value only. Canonical truth is wallets + transactions + wallet_adjustments. Not stored as independent balance truth. |
| derived_wallet_cash_balance | The Vault | The Vault | decimal | `1000.00` | Vault, Imperium, AI objective | backend | query/calculation | system_calculated | very_high | yes | no | summary_only | Derived display value for wallet_type `Cash`; not canonical storage. |
| derived_wallet_crypto_balance | The Vault | The Vault | decimal | `0.00` | Vault, Imperium, AI objective | backend | query/calculation | system_calculated | very_high | yes | no | summary_only | Derived display value for wallet_type `Crypto`; not canonical storage. |
| derived_wallet_total_balance | The Vault | The Vault | decimal | `1500.00` | Vault, Imperium, AI objective | backend | query/calculation | system_calculated | very_high | yes | no | summary_only | Sum derived from wallets + transactions + adjustments. |
| upcoming_expense_id | The Vault | The Vault | uuid | `ue_123` | Vault, Imperium, AI objective | backend | create/update | system_calculated | high | yes | yes | summary_only | Forecasting object, not real transaction. |
| upcoming_expense_label | The Vault | The Vault | string | `Loyer` | Vault, Imperium, AI objective | user/system | create/update | mixed | high | yes | yes | summary_only | Visible and editable. |
| upcoming_expense_amount | The Vault | The Vault | decimal | `400.00` | Vault, Imperium, AI objective | user/system | create/update | mixed | very_high | yes | yes | summary_only | Used in pressure and target. |
| upcoming_expense_due_date | The Vault | The Vault | date | `2026-05-05` | Vault, Imperium, AI objective | user/system | create/update | mixed | high | yes | yes | no | Sort by nearest due date first. |
| upcoming_expense_recurrence_type | The Vault | The Vault | enum | `monthly` | Vault, backend | user/system | create/update | user_confirmed | high | yes | yes | no | `none`, `weekly`, `monthly`, optional custom interval. |
| upcoming_expense_priority | The Vault | The Vault | enum | `critical` | Vault, Imperium, AI objective | user/system | create/update | mixed | high | yes | yes | summary_only | `critical`, `high`, `medium`, `low`. |
| upcoming_expense_source_type | The Vault | The Vault | enum | `manual` | Vault, backend | user/system | create/update | mixed | high | yes | yes | no | `manual`, `recurring`, `system_generated`. |
| remaining_charges | The Vault | The Vault | decimal | `900.00` | Vault, Imperium, AI objective | backend | transaction/upcoming update | system_calculated | very_high | yes | yes | summary_only | Minimum target formula input. |
| financial_pressure_score | The Vault | The Vault | integer/decimal | `72` | Vault, Imperium, AI advice | backend/rules | transaction/upcoming/period change | system_calculated | high | yes | yes | summary_only | Raw score should be deterministic in V1. |
| financial_pressure_label | The Vault | The Vault | enum | `DANGER` | Vault, Imperium, AI advice | backend/rules | pressure refresh | system_calculated | high | yes | yes | summary_only | Example labels: `SAFE`, `MODERE`, `DANGER`, `CRITIQUE`. |
| daily_minimal_target | The Vault | The Vault/AI | decimal | `150.00` | Vault, Imperium | backend/AI | daily/financial update | mixed | high | yes | yes | summary_only | Strict minimum. |
| daily_comfortable_target | The Vault | The Vault/AI | decimal | `250.00` | Vault, Imperium | backend/AI | daily/financial update | mixed | high | yes | yes | summary_only | Stabilizing target. |
| daily_optimal_target | The Vault | The Vault/AI | decimal | `400.00` | Vault, Imperium | backend/AI | daily/financial update | mixed | high | yes | yes | summary_only | Strong target. |
| weekly_real_profit | The Vault | The Vault | decimal | `1200.00` | The Path, Imperium, Vault | backend/user | weekly | mixed | very_high | yes | yes | summary_only | Input for sadaqa, not gross revenue. |

## Pulse Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| biological_profile_height | Pulse | Pulse | integer/decimal | `178` | Pulse, AI planner | user/AI/device | correction/review | mixed | high | yes | yes | summary_only | User corrects if AI is wrong. |
| biological_profile_current_weight | Pulse | Pulse | decimal | `82.5` | Pulse, AI planner | user/AI/device | correction/review | mixed | high | yes | yes | summary_only | Estimated current weight. |
| biological_profile_target_weight | Pulse | Pulse | decimal | `78.0` | Pulse, AI planner | user | correction/review | user_confirmed | high | yes | yes | summary_only | Health objective context. |
| biological_profile_age | Pulse | Pulse | integer | `TODO` | Pulse, AI planner | user | correction | user_confirmed | high | yes | yes | no | Source docs include age. |
| known_pain | Pulse | Pulse | array | `["knee"]` | Pulse, Imperium | user/AI/feedback | correction/workout feedback | mixed | very_high | yes | yes | summary_only | Protect pain zones. |
| injuries | Pulse | Pulse | array | `["shoulder injury"]` | Pulse, Imperium | user/AI/feedback | correction/workout feedback | mixed | very_high | yes | yes | summary_only | Workout constraints. |
| fatigue_state | Pulse | Pulse/Imperium | enum/number | `high` | Pulse, Imperium | user/wearable/AI | daily/session | mixed | high | yes | yes | summary_only | Can trigger workout adaptation/replanning. |
| sleep_issues | Pulse | Pulse | array/string | `short sleep` | Pulse, Imperium | user/wearable/AI | daily/weekly | mixed | very_high | yes | yes | summary_only | Part of biological truth. |
| mobility_limitations | Pulse | Pulse | array | `["limited squat depth"]` | Pulse | user/AI | correction | mixed | very_high | yes | yes | summary_only | Workout realism. |
| health_objective | Pulse | Pulse | string | `fat loss` | Pulse, Imperium | user/AI | correction/review | user_confirmed | high | yes | yes | summary_only | Exact taxonomy TODO. |
| health_score | Pulse | Pulse | integer | `82` | Pulse, Imperium | backend/AI | daily/weekly | mixed | high | yes | yes | summary_only | Must not appear without explanation. |
| health_score_confidence | Pulse | Pulse | enum/decimal | `high` | Pulse, Imperium | backend/AI | score refresh | mixed | high | yes | yes | summary_only | Missing data lowers confidence. |
| health_score_positive_factors | Pulse | Pulse | array | `["recovery correct"]` | Pulse | backend/AI | score refresh | ai_inferred | high | yes | conditional | summary_only | Display explanation. |
| health_score_negative_factors | Pulse | Pulse | array | `["hydration low"]` | Pulse | backend/AI | score refresh | ai_inferred | high | yes | conditional | summary_only | Display explanation. |
| sleep_duration | Pulse | Pulse/Wearable | decimal nullable | `6.5` | Pulse, Imperium | wearable/user | daily | mixed | very_high | yes | yes | summary_only | Wearable optional. |
| sleep_quality | Pulse | Pulse/Wearable | enum/number nullable | `medium` | Pulse, Imperium | wearable/user | daily | mixed | very_high | yes | yes | summary_only | Exact scale TODO. |
| hydration_level | Pulse | Pulse | enum/number | `low` | Pulse, Imperium | user/AI | daily | mixed | high | yes | yes | summary_only | Nutrition/health score input. |
| protein_intake | Pulse | Pulse | decimal | `120` | Pulse | user/AI | daily | mixed | high | yes | yes | summary_only | Unit grams assumed; TODO confirm. |
| recovery_state | Pulse | Pulse/Wearable | enum/number | `moderate` | Pulse, Imperium | wearable/user/AI | daily | mixed | high | yes | yes | summary_only | Not used by Vector V1; Imperium/Pulse handle health constraints. |
| workout_title | Pulse | Pulse | string | `Mobility and push session` | Pulse, Imperium | AI/backend | daily/request | ai_inferred | medium | yes | yes | summary_only | Must be executable. |
| workout_duration | Pulse | Pulse | integer | `35` | Pulse, Imperium | AI/backend | daily/request | ai_inferred | medium | yes | yes | no | Minutes. |
| workout_intensity | Pulse | Pulse | enum | `low` | Pulse, Imperium | AI/backend | daily/request/adaptation | ai_inferred | high | yes | yes | summary_only | Protects pain/fatigue. |
| workout_exercises | Pulse | Pulse | array | `["walk","mobility"]` | Pulse | AI/backend | daily/request | ai_inferred | high | yes | yes | summary_only | Exact exercise schema TODO. |
| workout_adaptation_reason | Pulse | Pulse | enum | `fatigue` | Pulse, Imperium | user/AI/backend | adaptation trigger | mixed | high | yes | yes | summary_only | Fatigue, lack of time, pain, injury, no equipment, unexpected event. |
| available_equipment | Pulse | Pulse | array | `["dumbbells"]` | Pulse | user/location | daily/request | mixed | medium | yes | yes | summary_only | Used for realistic workout. |
| stock_item_id | Pulse | Pulse | uuid | `stock_123` | Pulse, nutrition, grocery | backend | stock create | system_calculated | medium | yes | yes | no | Inventory object. |
| stock_item_name | Pulse | Pulse | string | `chicken breast` | Pulse, nutrition, grocery | user/OCR | stock update | mixed | medium | yes | yes | summary_only | Ticket scan can update stock. |
| stock_quantity | Pulse | Pulse | decimal | `3` | Pulse, nutrition, batch cooking | user/OCR/backend | stock update/cooking | mixed | medium | yes | yes | no | Decreases after cooking. |
| stock_unit | Pulse | Pulse | string | `pieces` | Pulse | user/OCR | stock update | mixed | low | yes | yes | no | Unit taxonomy TODO. |
| stock_expiry_type | Pulse | Pulse | enum | `DLC` | Pulse, nutrition | user/OCR | stock update | mixed | medium | yes | yes | no | `DLC` strict, `DDM` flexible. |
| stock_expiry_date | Pulse | Pulse | date nullable | `2026-04-27` | Pulse, nutrition | user/OCR | stock update | mixed | medium | yes | yes | no | Close DLC triggers alerts. |
| grocery_list_items | Pulse | Pulse | array | `["rice","eggs"]` | Pulse, Imperium | Pulse/user | list generation/update | mixed | medium | yes | yes | summary_only | User can modify everything. |
| batch_cooking_plan | Pulse | Pulse | object | `{"meals":6,"cost_per_meal":2.8}` | Pulse, Vault, Imperium | AI/backend | weekly/request | ai_inferred | medium | yes | yes | summary_only | After validation, stock decreases and cooked meals increase. |
| wearable_hr | Pulse | Wearable | integer nullable | `72` | Pulse | wearable | sync | device_reported | very_high | conditional | yes | no | System must work without it. |
| wearable_hrv | Pulse | Wearable | decimal nullable | `48` | Pulse | wearable | sync | device_reported | very_high | conditional | yes | no | Improves precision. |
| wearable_steps | Pulse | Wearable | integer nullable | `8200` | Pulse | wearable | sync | device_reported | high | conditional | yes | summary_only | Optional. |

## The Path Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| next_prayer_name | The Path | The Path | enum | `Asr` | Path, Imperium, Pulse | Path/backend | daily/location refresh | mixed | high | yes | yes | no | Prayer anchors are non-negotiable. |
| next_prayer_time | The Path | The Path | timestamp | `2026-04-25T18:12:00+02:00` | Path, Imperium, Pulse | Path/external/calculation | daily/location refresh | mixed | high | yes | yes | no | Mosque reality first via MAWAQIT when available. |
| full_prayer_times | The Path | The Path | object | `{"fajr":"04:35","dhuhr":"13:48"}` | Path, Imperium | Path/external/calculation | daily/location refresh | mixed | high | yes | yes | no | Full 5 prayers. |
| prayer_countdown_seconds | The Path | The Path | integer | `3400` | Path UI, Imperium | backend/UI | live | system_calculated | low | yes | conditional | no | Usually computed. |
| prayer_source | The Path | The Path | enum | `mawaqit` | Path, Imperium | Path/backend | daily/location refresh | mixed | high | yes | yes | no | Fallback: calculation engine with method, madhhab, location accuracy. |
| mawaqit_data_quality | The Path | External/The Path | enum/decimal | `high` | Path, Imperium | external feed/backend | prayer refresh | external_feed | medium | yes | yes | no | Exact scale TODO. |
| qibla_direction_degrees | The Path | The Path | decimal | `119.4` | Path | backend/calculation | location refresh | system_calculated | medium | yes | conditional | no | Mentioned in global overview. |
| ghusl_required | The Path | The Path | boolean | `true` | Path, Imperium | user | manual activation/completion | user_confirmed | very_high | yes | yes | summary_only | Activation only manual because religious privacy. |
| ghusl_required_since | The Path | The Path | timestamp | `2026-04-25T09:00:00+02:00` | Path, Imperium | user/backend | activation | user_confirmed | very_high | yes | yes | no | Triggers automatic mission. |
| ghusl_mission_id | The Path | Imperium/The Path | uuid | `mis_ghusl_asr` | Path, Imperium | backend | activation/planning | system_calculated | very_high | yes | yes | summary_only | Example mission: `Faire le ghusl avant Asr`. |
| registered_ghusl_addresses | The Path | The Path | array | `["home"]` | Path, Imperium | user | settings change | user_confirmed | very_high | yes | yes | summary_only | Exact schema TODO. |
| fasting_active | The Path | The Path | boolean | `true` | Path, Pulse, Imperium | user/calendar/backend | daily | mixed | high | yes | yes | summary_only | Affects biology and planning. |
| fasting_type | The Path | The Path | enum | `monday_thursday` | Path, Pulse, Imperium | user/calendar/backend | daily | mixed | high | yes | yes | summary_only | Monday/Thursday, white days, Ramadan, custom, temporary. |
| suhoor_time | The Path | The Path | timestamp nullable | `2026-04-25T04:20:00+02:00` | Pulse, Imperium | Path/backend | fasting day | mixed | high | yes | yes | no | Sent as Pulse constraint. |
| iftar_time | The Path | The Path | timestamp nullable | `2026-04-25T21:04:00+02:00` | Pulse, Imperium | Path/backend | fasting day | mixed | high | yes | yes | no | Sent as Pulse constraint. |
| hydration_limits | The Path | The Path/Pulse | object | `{"daytime":false}` | Pulse | Path/backend | fasting day | system_calculated | high | yes | yes | summary_only | Constraint, not nutrition advice by itself. |
| hijri_date | The Path | The Path | string | `13 Shawwal 1447` | Path, Imperium | lunar calendar engine | daily | mixed | medium | yes | yes | no | Exact calendar source TODO. |
| lunar_month | The Path | The Path | string | `Shawwal` | Path | lunar calendar engine | daily | mixed | medium | yes | yes | no | Used for fasting windows. |
| white_days_active | The Path | The Path | boolean | `true` | Path, Pulse, Imperium | lunar calendar engine | monthly | mixed | medium | yes | yes | summary_only | 13/14/15 should trigger preparation. |
| quran_page | The Path | The Path | integer | `122` | Path, Imperium | user | reading validation | user_confirmed | high | yes | yes | summary_only | Reopen at continuation point. |
| quran_juz | The Path | The Path | integer | `7` | Path | backend/user | reading validation | mixed | medium | yes | yes | no | Continuation metadata. |
| quran_hizb | The Path | The Path | string/integer | `13` | Path | backend/user | reading validation | mixed | medium | yes | yes | no | Continuation metadata. |
| quran_surah | The Path | The Path | string | `Al-Ma'idah` | Path | backend/user | reading validation | mixed | medium | yes | yes | summary_only | ASCII transliteration preferred until UI decides. |
| quran_last_validated_point | The Path | The Path | object | `{"page":122}` | Path, Imperium | user | validation | user_confirmed | high | yes | yes | summary_only | No restart friction. |
| quran_daily_objective | The Path | The Path | string/object | `2 pages` | Path, Imperium | user/AI | daily/weekly | mixed | high | yes | yes | summary_only | Routine discipline inside Imperium. |
| adhkar_routine_id | The Path | The Path | uuid | `adhkar_morning` | Path, Imperium | user/backend | settings/create | user_confirmed | high | yes | yes | summary_only | Trackable and repeatable. |
| adhkar_type | The Path | The Path | enum | `istighfar` | Path, Imperium | user | settings/create | user_confirmed | high | yes | yes | summary_only | Morning, evening, istighfar, salawat, tasbih, tahmid, takbir, personal. |
| adhkar_target_count | The Path | The Path | integer | `100` | Path, Imperium | user | settings/create | user_confirmed | high | yes | yes | summary_only | Example: Istighfar 100. |
| adhkar_completed_count | The Path | The Path | integer | `60` | Path, Imperium | user | completion | user_confirmed | high | yes | yes | summary_only | Affects discipline score. |
| sadaqa_percentage | The Path | The Path | decimal | `0.05` | Path, Vault | user | setting change | user_confirmed | very_high | yes | yes | summary_only | Example 5 percent weekly. |
| sadaqa_weekly_target | The Path | The Path/The Vault | decimal | `60.00` | Path, Imperium | backend | weekly profit refresh | system_calculated | very_high | yes | yes | summary_only | Based on real weekly profit. |
| sadaqa_remaining_carry | The Path | The Path | decimal | `20.00` | Path, Imperium | backend/user | weekly/donation | mixed | very_high | yes | yes | summary_only | Critical carry behavior. |
| sadaqa_donation_amount | The Path | The Path | decimal | `40.00` | Path, Vault, learning | user | donation validation | user_confirmed | very_high | yes | yes | summary_only | User confirms `JAI DONNE`. |
| sadaqa_destination | The Path | The Path | string | `local charity` | Path | user | donation validation | user_confirmed | very_high | yes | yes | summary_only | Optional note may exist. |

## AI Routing Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ai_request_id | AI routing | Core | uuid | `air_123` | n8n, AI router, logs | backend | per AI request | system_calculated | high | yes | yes | no | Trace every model call. |
| request_source_app | AI routing | Client apps | enum | `Imperium` | AI router, n8n | app/backend | per request | system_calculated | low | yes | yes | no | Source app is a first routing dimension. |
| input_type | AI routing | Client apps/Core | enum | `image` | AI router | app/backend | per request | system_calculated | medium | yes | yes | no | Text, audio, image, screenshot, document, event, sensor. |
| urgency_level | AI routing | Client apps/Core | enum | `real_time` | AI router, n8n | app/backend | per request | mixed | medium | yes | yes | no | Exact SLA thresholds TODO. |
| latency_target_ms | AI routing | Core | integer nullable | `1500` | AI router, n8n | backend | per request | TODO | low | yes | yes | no | Numeric targets TODO. |
| cost_sensitivity | AI routing | Core | enum | `low_cost` | AI router | backend/user policy | per request | system_calculated | medium | yes | yes | no | Prefer local when possible. |
| request_privacy_level | AI routing | Core | enum | `very_high` | AI router, n8n | backend/app | per request | mixed | high | yes | yes | no | Determines local-first or minimal external payload. |
| complexity_level | AI routing | Core | enum | `complex_strategy` | AI router | Qwen/router/rules | per request | ai_inferred | medium | yes | yes | summary_only | Deterministic, simple, contextual, complex, multimodal. |
| audio_length_seconds | AI routing | Core | integer nullable | `42` | AI router, transcription workflow | app/backend | audio request | device_reported | very_high | yes | yes | no | Routes Whisper/faster-whisper profile. |
| image_ocr_required | AI routing | Core | boolean | `true` | AI router | app/backend | per request | system_calculated | high | yes | yes | no | Routes to Gemini. |
| offline_required | AI routing | Core | boolean | `false` | AI router | app/backend | per request | device_reported | high | yes | yes | no | Forces local-only when true. |
| long_term_memory_required | AI routing | Core | boolean | `true` | AI router, n8n | backend/app | per request | mixed | high | yes | yes | no | Determines PG/pgvector read/write. |
| selected_model | AI routing | Core | enum | `Gemini` | n8n, AI logs | AI router | per request | system_calculated | medium | yes | yes | no | Qwen E2B/E4B, Gemini, GPT, Claude, Whisper/faster-whisper. |
| selected_workflow | AI routing | n8n | string | `vault_receipt_ocr` | n8n, backend | AI router/n8n | per request | system_calculated | medium | yes | yes | no | Workflow names TODO. |
| routing_reason | AI routing | Core | text | `image OCR required` | logs, debug, learning | AI router | per request | system_calculated | medium | yes | yes | summary_only | Must be explainable. |
| model_confidence | AI routing | Core | decimal nullable | `0.88` | n8n, apps, learning | model/router | per response | ai_inferred | medium | yes | yes | summary_only | Display where useful, especially OCR/health. |
| model_output_type | AI routing | Core | enum | `recommendation` | n8n, app | AI router/model | per response | system_calculated | low | yes | yes | no | Recommendation, extraction, transcription, advice, summary, action plan. |

## External Data Variables

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rail_status | external_data | External | object | `{"line":"RER B","status":"delays"}` | Vector, Imperium | external feed/n8n | feed refresh | external_feed | low | yes | conditional | summary_only | IDFM/rail source mentioned; provider details TODO. |
| event_signal | external_data | External | object | `{"type":"concert","area":"Bercy"}` | Vector | external feed/n8n | feed refresh | external_feed | low | yes | conditional | summary_only | Events/concerts source TODO. |
| traffic_state | external_data | External | object | `{"area":"A86","level":"heavy"}` | Vector, Path, Pulse | external feed/n8n | feed refresh | external_feed | low | yes | conditional | summary_only | Traffic provider TODO. Vector uses only VTC-operational impact. |
| road_closure_signal | external_data | External | object | `{"road":"TODO","active":true}` | Vector | external feed/n8n | feed refresh | external_feed | low | yes | conditional | no | Provider TODO. |
| airport_code | external_data | External/Vector | enum | `CDG` | Vector | flight data/n8n | flight refresh | external_feed | low | yes | conditional | no | CDG/Orly in source docs. |
| airport_terminal | external_data | External/Vector | string | `2E` | Vector | flight data/n8n | flight refresh | external_feed | low | yes | conditional | no | Used for passenger availability delay. |
| flight_landing_time | external_data | External/Vector | timestamp | `2026-04-25T08:40:00+02:00` | Vector | flight data/n8n | flight refresh | external_feed | low | yes | conditional | no | Landing is not immediate demand. |
| flight_type | external_data | External/Vector | enum | `international_non_schengen` | Vector | flight data/n8n | flight refresh | external_feed | low | yes | conditional | summary_only | Domestic vs international, Schengen vs non-Schengen. |
| passenger_delay_estimate_minutes | external_data | Vector | integer | `35` | Vector | backend/learning | flight/airport analysis | mixed | low | yes | conditional | summary_only | Includes taxiing, border, baggage, exit, booking delay. |
| airport_demand_window_start | external_data | Vector | timestamp | `2026-04-25T09:15:00+02:00` | Vector | backend/learning | flight/airport analysis | mixed | low | yes | conditional | summary_only | Real VTC demand window. |
| mawaqit_prayer_times | external_data | External/The Path | object | `{"asr":"18:12"}` | Path, Imperium | MAWAQIT/n8n | daily/location refresh | external_feed | high | yes | yes | no | First priority source when available. |
| maps_eta | external_data | External/Vector | integer | `10` | Vector, Path, Pulse | maps provider/n8n | per route | external_feed | medium | yes | conditional | no | Adjusted by learned real multiplier. |

## Derived Scores

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| financial_pressure_score | derived_scores | The Vault | integer/decimal | `72` | Vault, Imperium, AI router | backend/rules | financial refresh | system_calculated | high | yes | yes | summary_only | Duplicate cross-reference from Vault category. |
| daily_objective_minimal | derived_scores | The Vault | decimal | `150.00` | Vault, Imperium | backend/AI | daily/financial refresh | mixed | high | yes | yes | summary_only | Remaining charges / remaining useful days. |
| daily_objective_comfortable | derived_scores | The Vault | decimal | `250.00` | Vault, Imperium | backend/AI | daily/financial refresh | mixed | high | yes | yes | summary_only | Coefficient logic; exact coefficient dynamic. |
| daily_objective_optimal | derived_scores | The Vault | decimal | `400.00` | Vault, Imperium | backend/AI | daily/financial refresh | mixed | high | yes | yes | summary_only | Coefficient logic; exact coefficient dynamic. |
| health_score | derived_scores | Pulse | integer | `82` | Pulse, Imperium | backend/AI | daily/weekly | mixed | high | yes | yes | summary_only | Must include explanation and confidence. |
| energy_score | derived_scores | Imperium/Pulse | integer nullable | `72` | Imperium, Pulse | TODO | TODO | TODO | high | yes | yes | summary_only | Model postponed. |
| discipline_score | derived_scores | Imperium/Core | integer nullable | `81` | Imperium, Path, Pulse | backend/AI | daily/weekly | mixed | high | yes | yes | summary_only | Model postponed. |
| vector_hourly_rate_score | derived_scores | Vector | decimal | `54.20` | Vector | backend/rules | ride analysis | system_calculated | high | yes | yes | summary_only | Highest ride evaluation priority. |
| dead_return_risk_score | derived_scores | Vector | decimal | `0.68` | Vector | rules/AI | ride analysis | mixed | high | yes | yes | summary_only | Avoid fake profitability. |
| airport_value_score | derived_scores | Vector | decimal | `0.64` | Vector | rules/AI/external | ride/position analysis | mixed | medium | yes | yes | summary_only | Uses real demand window. |
| event_value_score | derived_scores | Vector | decimal | `0.41` | Vector | rules/external | ride/position analysis | mixed | medium | yes | yes | summary_only | Source TODO. |
| recommendation_quality_score | derived_scores | Vector/Core | decimal | `0.79` | learning, Vector | backend/learning | after feedback/session | mixed | high | yes | yes | summary_only | Exact scoring TODO. |
| nutrition_confidence | derived_scores | Pulse | decimal/enum | `medium` | Pulse | AI/backend | plan generation | mixed | high | yes | yes | summary_only | Missing data lowers confidence. |
| planning_confidence_level | derived_scores | Imperium/Core | enum | `reduced` | Imperium, AI advice | backend/AI | weekly/replan/anomaly | mixed | high | yes | yes | summary_only | Decreases when review overdue. |
| mission_intensity_level | derived_scores | Imperium/Pulse | enum | `normal` | Imperium, Pulse | AI/backend | mission generation/replan | mixed | high | yes | yes | summary_only | Exact enum TODO. |

## Feedback and Learning

| variable_name | category | source_app | data_type | example_value | read_by | written_by | update_frequency | reliability_level | privacy_level | used_for_decision | stored_in_postgres | stored_in_vector_memory | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| feedback_id | feedback_learning | Core | uuid | `fb_123` | n8n, learning, AI router | backend | feedback create | system_calculated | high | yes | yes | no | Canonical feedback event. |
| feedback_source_app | feedback_learning | Client apps | enum | `Vector` | n8n, learning | app/backend | feedback create | system_calculated | low | yes | yes | no | Source app. |
| feedback_type | feedback_learning | Core | enum | `bad_recommendation` | learning, AI router | app/user/backend | feedback create | user_confirmed | high | yes | yes | summary_only | Exact taxonomy TODO. |
| user_satisfaction | feedback_learning | Core | enum/number | `low` | learning, AI router | user/app | feedback create | user_confirmed | high | yes | yes | summary_only | Optional depending on workflow. |
| mission_completion_event | feedback_learning | Imperium | object | `{"mission_id":"mis_123","status":"done"}` | Imperium, learning | user/backend | mission done | user_confirmed | high | yes | yes | summary_only | Learning signal, not just UI event. |
| mission_failure_event | feedback_learning | Imperium | object | `{"reason":"fatigue"}` | Imperium, learning | user/backend | mission not done | user_confirmed | high | yes | yes | summary_only | Failure is information. |
| replanning_event | feedback_learning | Imperium | object | `{"reason":"priority_shift"}` | Imperium, learning | user/backend | replanning | user_confirmed | high | yes | yes | summary_only | Traceable correction path. |
| weekly_review_summary | feedback_learning | Imperium | object/text | `3 structural changes detected` | all planners, learning | user/AI/backend | weekly completion | mixed | very_high | yes | yes | yes | Major memory object. |
| user_correction | feedback_learning | Core | object | `{"field":"weight","corrected_to":82.5}` | learning, app | user | correction | user_confirmed | very_high | yes | yes | summary_only | Applies across Pulse, Vector, Vault, Path, Imperium. |
| recommendation_accepted | feedback_learning | Vector | boolean | `true` | Vector learning | user | ride decision | user_confirmed | high | yes | yes | summary_only | Accepted/refused rides train strategy. |
| recommendation_refused | feedback_learning | Vector | boolean | `false` | Vector learning | user | ride decision | user_confirmed | high | yes | yes | summary_only | Complement to accepted. |
| actual_reposition_outcome | feedback_learning | Vector | object | `{"zone":"Orly","result":"good"}` | Vector learning | user/session/backend | session/reposition end | mixed | high | yes | yes | summary_only | Improves local adaptation. |
| actual_profitability | feedback_learning | Vector/The Vault | decimal | `42.8` | Vector, Vault, learning | backend | session end | system_calculated | high | yes | yes | summary_only | Used for rule evolution. |
| bad_ai_extraction_flag | feedback_learning | Core | boolean | `true` | AI router, learning | user/app | correction | user_confirmed | high | yes | yes | summary_only | OCR/transcription correction. |
| memory_embedding_id | feedback_learning | Core/pgvector | uuid | `emb_123` | AI router, n8n | memory pipeline | embedding write | system_calculated | high | yes | yes | yes | Link structured object to semantic memory. |
| learning_pattern_id | feedback_learning | Core/pgvector | uuid | `pat_123` | AI router, n8n | learning pipeline | pattern update | mixed | high | yes | yes | yes | Patterns must be explainable and reversible. |
| business_rule_version | feedback_learning | Vector/Core | string | `vtc_rules_v3` | Vector, n8n, AI router | learning/admin/user validation | rule update | mixed | high | yes | yes | summary_only | Business rules must be versioned. |
