# NBN23 SWISH API Reference
# Israeli Basketball Data API (ibasketball.co.il)

## API Configuration

BASE_URL = "https://api.swish.nbn23.com"
AUTHENTICATION = None  # Public API, no auth required

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://ibasketball.co.il",
    "User-Agent": "Mozilla/5.0"
}

## Endpoints

### 1. GET /seasons
Returns all available seasons.

Response:
```json
[
  {
    "_id": "686e1422dd2c672160d5ca4b",
    "name": "2025/2026",
    "startDate": "2025-08-01T00:00:00.000Z",
    "endDate": "2026-07-31T23:59:59.999Z"
  }
]
```

### 2. GET /competitions?seasonId={seasonId}
Returns all competitions/leagues for a season.

Response:
```json
[
  {
    "id": "68b7692435d423fc80c405ec",
    "name": "ליגת על",
    "projectKey": "ibba",
    "groups": [
      {
        "id": "68b7692435d423fc80c405ed",
        "name": "רגילה",
        "order": 1,
        "type": "LEAGUE"
      }
    ]
  }
]
```

### 3. GET /calendar?groupId={groupId}
Returns all matches for a competition group.

Response:
```json
{
  "id": "68cc83769569a17980f47da2",
  "type": "LEAGUE",
  "name": "רגילה",
  "rounds": [
    {
      "endDate": "2025-12-16",
      "matches": [
        {
          "id": "68cc83769569a17980f47dbf",
          "homeTeam": {
            "id": "68cc83769569a17980f47db5",
            "name": "בני יהודה תל אביב",
            "logo": "..."
          },
          "awayTeam": {
            "id": "68cc83769569a17980f47db6",
            "name": "הפועל הוד השרון",
            "logo": "..."
          },
          "date": "2025-10-28T19:00:00.000Z",
          "score": {
            "totals": [
              {"teamId": "...", "total": 66},
              {"teamId": "...", "total": 59}
            ]
          },
          "status": "CLOSED",
          "court": {
            "place": "אולם ספורט, תל אביב",
            "address": null,
            "town": null
          }
        }
      ]
    }
  ]
}
```

Match status values: "NOT_STARTED", "LIVE", "CLOSED"

### 4. GET /standings?groupId={groupId}
Returns standings/league table.

Response:
```json
[
  {
    "teamId": "...",
    "name": "מכבי תל אביב",
    "position": 1,
    "logo": "...",
    "stats": {
      "playedMatches": 4,
      "wonMatches": 3,
      "lostMatches": 1,
      "pointsPerGame": 75.25,
      "opponentsPointsPerGame": 66.75
    }
  }
]
```

## Known Season IDs

SEASONS = {
    "2025/2026": "686e1422dd2c672160d5ca4b",
    "2024/2025": "668ba5c2ceb8a7aa70c41ae2", 
    "2023/2024": "648068e5f237bcc9c859a66a",
    "2022/2023": "61ee7ed011e06ff312049ae1",
}

## Data Flow

seasons → seasonId → competitions → groups[].id → calendar/standings

## Notes

- All dates are UTC (ISO 8601 with Z suffix)
- Team/competition names are in Hebrew (UTF-8)
- Group types: "LEAGUE" (regular season), "PLAYOFF" (knockout)
- No rate limiting observed, but be respectful
