# SpeakNode Kotlin Client

Compose Multiplatform Desktop client for SpeakNode.

## Requirements

- JDK 17+
- Gradle 8.11+ (wrapper included)

## Build & Run

```bash
# Generate Gradle wrapper (first time only)
gradle wrapper

# Run
./gradlew run

# Create distribution package
./gradlew packageDeb       # Linux
./gradlew packageDmg       # macOS
./gradlew packageMsi       # Windows
```

## Architecture

```
kotlin-client/
├── build.gradle.kts                         # Build config (Compose + Ktor)
├── src/main/kotlin/com/speaknode/client/
│   ├── Main.kt                              # Entry point
│   ├── api/
│   │   ├── SpeakNodeApi.kt                  # HTTP client (Ktor)
│   │   └── models/ApiModels.kt              # Request/Response models
│   ├── ui/
│   │   ├── App.kt                           # Root Composable
│   │   ├── theme/Theme.kt                   # Material 3 dark theme
│   │   ├── components/Sidebar.kt            # Navigation sidebar
│   │   └── screens/
│   │       ├── MeetingScreen.kt             # Meeting analysis/list
│   │       └── AgentScreen.kt               # AI Agent conversation
│   └── viewmodel/
│       ├── AppViewModel.kt                  # Global state management
│       └── AgentViewModel.kt                # Agent conversation state
```

## Tech Stack

| Domain | Stack |
|--------|-------|
| UI | Compose Multiplatform (Material 3) |
| HTTP | Ktor Client (CIO engine) |
| Serialization | Kotlinx Serialization |
| Async | Kotlinx Coroutines |
| Build | Gradle Kotlin DSL |

## API Endpoints (Python Server)

Default server address: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |
| GET | `/chats` | List chat sessions |
| POST | `/chats` | Create chat session |
| DELETE | `/chats/{id}` | Delete chat session |
| POST | `/analyze` | Analyze audio |
| POST | `/agent/query` | Agent query |
| GET | `/meetings` | List meetings |
| GET | `/meetings/{id}` | Meeting details |
| GET | `/graph/export` | Export graph |
| POST | `/graph/import` | Import graph |
| PATCH | `/nodes/update` | Update node |

## Server Configuration

CORS allowed origins are configured via environment variable:

```bash
export SPEAKNODE_CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
```
