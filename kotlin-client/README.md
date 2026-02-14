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
├── build.gradle.kts                         # Build config (Compose 1.7.3 + Ktor 3.0.3)
├── settings.gradle.kts
├── gradle.properties
├── src/main/kotlin/com/speaknode/client/
│   ├── Main.kt                              # Entry point (1200×800 window)
│   ├── api/
│   │   ├── SpeakNodeApi.kt                  # Ktor HTTP client (all endpoints as suspend functions)
│   │   └── models/ApiModels.kt              # @Serializable request (4) / response (10) models
│   ├── ui/
│   │   ├── App.kt                           # Root Composable (2-pane layout: sidebar + content)
│   │   ├── theme/Theme.kt                   # Material 3 dark theme (primary=#7C4DFF, secondary=#00E676)
│   │   ├── components/
│   │   │   └── Sidebar.kt                   # Sidebar (260dp): server status, chat list, navigation
│   │   └── screens/
│   │       ├── MeetingScreen.kt             # Meeting analysis/list (file path input, status indicator, cards)
│   │       └── AgentScreen.kt               # AI Agent conversation (chat bubbles, example questions, Enter key)
│   └── viewmodel/
│       ├── AppViewModel.kt                  # Global state (ServerStatus, chatIds, meetings, analysisState)
│       └── AgentViewModel.kt                # Agent conversation state (messages, isLoading)
```

## Component Details

### UI Layout

```
Window (1200×800)
└─ App.kt (Root Composable)
     ├─ Sidebar (260dp fixed width)
     │   ├─ Server status indicator (StatusIndicator)
     │   ├─ Navigation tabs (Meetings / Agent)
     │   ├─ Chat session create/select/delete
     │   └─ Refresh button
     └─ Content Area
         ├─ MeetingScreen
         │   ├─ Audio file path input + analysis trigger
         │   ├─ Analysis state display (Idle → Analyzing → Complete/Error)
         │   └─ Meeting cards list (LazyColumn)
         └─ AgentScreen
             ├─ Chat bubble UI (user/assistant/error)
             ├─ Example question buttons
             ├─ Enter key send support
             └─ Conversation history reset
```

### ViewModel Layer

| ViewModel | State (StateFlow) |
|---|---|
| `AppViewModel` | `serverStatus`, `chatIds`, `activeChatId`, `meetings`, `analysisState`, `error` |
| `AgentViewModel` | `messages`, `isLoading` |

### API Layer

`SpeakNodeApi` wraps all FastAPI endpoints as Kotlin `suspend` functions using Ktor CIO engine with JSON content negotiation (Kotlinx Serialization).

## Tech Stack

| Domain | Stack | Version |
|--------|-------|---------|
| UI Framework | Compose Multiplatform | 1.7.3 |
| Kotlin | JVM | 2.1.0 |
| HTTP Client | Ktor (CIO engine) | 3.0.3 |
| Serialization | Kotlinx Serialization | 1.7.3 |
| Async | Kotlinx Coroutines | 1.9.0 |
| Theme | Material 3 Dark | (Compose built-in) |
| Build | Gradle Kotlin DSL | 8.11+ |

## API Endpoints (Python Server)

Default server address: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |
| GET | `/chats` | List chat sessions |
| POST | `/chats` | Create chat session |
| DELETE | `/chats/{id}` | Delete chat session |
| POST | `/analyze` | Analyze audio (multipart file upload) |
| POST | `/agent/query` | Agent query |
| GET | `/meetings` | List meetings |
| GET | `/meetings/{id}` | Meeting details |
| GET | `/graph/export` | Export graph (optional `include_embeddings`) |
| POST | `/graph/import` | Import graph dump |
| PATCH | `/nodes/update` | Update node properties |

## Server Configuration

CORS allowed origins are configured via environment variable:

```bash
export SPEAKNODE_CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
```
