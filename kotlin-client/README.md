# SpeakNode Kotlin Client

Compose Multiplatform Desktop 기반 SpeakNode 클라이언트.

## Requirements

- JDK 17+
- Gradle 8.11+ (wrapper 포함)

## Build & Run

```bash
# Gradle wrapper 생성 (최초 1회)
gradle wrapper

# 실행
./gradlew run

# 배포 패키지 생성
./gradlew packageDeb       # Linux
./gradlew packageDmg       # macOS
./gradlew packageMsi       # Windows
```

## Architecture

```
kotlin-client/
├── build.gradle.kts                         # 빌드 설정 (Compose + Ktor)
├── src/main/kotlin/com/speaknode/client/
│   ├── Main.kt                              # 엔트리포인트
│   ├── api/
│   │   ├── SpeakNodeApi.kt                  # HTTP 클라이언트 (Ktor)
│   │   └── models/ApiModels.kt              # Request/Response 모델
│   ├── ui/
│   │   ├── App.kt                           # 루트 Composable
│   │   ├── theme/Theme.kt                   # Material 3 다크 테마
│   │   ├── components/Sidebar.kt            # 네비게이션 사이드바
│   │   └── screens/
│   │       ├── MeetingScreen.kt             # 회의 분석/목록
│   │       └── AgentScreen.kt               # AI Agent 대화
│   └── viewmodel/
│       ├── AppViewModel.kt                  # 전역 상태 관리
│       └── AgentViewModel.kt                # Agent 대화 상태
```

## Tech Stack

| Domain | Stack |
|--------|-------|
| UI | Compose Multiplatform (Material 3) |
| HTTP | Ktor Client (CIO engine) |
| Serialization | Kotlinx Serialization |
| Async | Kotlinx Coroutines |
| Build | Gradle Kotlin DSL |

## API Endpoints (Python 서버)

서버 기본 주소: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | 서버 상태 확인 |
| GET | `/chats` | 채팅 목록 |
| POST | `/chats` | 채팅 생성 |
| DELETE | `/chats/{id}` | 채팅 삭제 |
| POST | `/analyze` | 오디오 분석 |
| POST | `/agent/query` | Agent 질의 |
| GET | `/meetings` | 회의 목록 |
| GET | `/meetings/{id}` | 회의 상세 |
| GET | `/graph/export` | 그래프 내보내기 |
| POST | `/graph/import` | 그래프 가져오기 |
| PATCH | `/nodes/update` | 노드 수정 |

## Server Configuration

CORS 허용 origin은 환경 변수로 설정:

```bash
export SPEAKNODE_CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
```
