package com.speaknode.client.api

import com.speaknode.client.api.models.*
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.engine.cio.*
import io.ktor.client.plugins.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.plugins.logging.*
import io.ktor.client.request.*
import io.ktor.client.request.forms.*
import io.ktor.client.statement.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import io.ktor.utils.io.*
import kotlinx.coroutines.delay
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive
import java.io.Closeable
import java.io.File
import java.net.ConnectException

/**
 * HTTP client for communicating with the SpeakNode FastAPI server.
 *
 * All API endpoints are provided as coroutine-based suspend functions.
 * Includes automatic retry with exponential backoff for transient failures.
 */
class SpeakNodeApi(
    private val baseUrl: String = "http://localhost:8000",
) : Closeable {

    companion object {
        private const val MAX_RETRIES = 3
        private const val INITIAL_DELAY_MS = 500L
    }

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    private val client = HttpClient(CIO) {
        install(ContentNegotiation) {
            json(this@SpeakNodeApi.json)
        }
        install(Logging) {
            level = LogLevel.NONE
        }
        install(HttpTimeout) {
            requestTimeoutMillis = 300_000
            connectTimeoutMillis = 10_000
        }
        defaultRequest {
            contentType(ContentType.Application.Json)
        }
    }

    /**
     * Retry wrapper with exponential backoff.
     * Only retries on transient errors (connection, timeout, 5xx).
     */
    private suspend fun <T> withRetry(
        maxRetries: Int = MAX_RETRIES,
        operation: suspend () -> T,
    ): T {
        var lastException: Exception? = null
        repeat(maxRetries) { attempt ->
            try {
                return operation()
            } catch (e: Exception) {
                lastException = e
                if (!isRetryable(e) || attempt == maxRetries - 1) {
                    throw toUserFriendlyException(e)
                }
                val delayMs = INITIAL_DELAY_MS * (1L shl attempt) // 500, 1000, 2000...
                delay(delayMs)
            }
        }
        throw toUserFriendlyException(lastException ?: RuntimeException("Unknown error"))
    }

    private fun isRetryable(e: Exception): Boolean = when (e) {
        is ConnectException -> true
        is java.net.SocketTimeoutException -> true
        is io.ktor.client.plugins.HttpRequestTimeoutException -> true
        is ServerResponseException -> e.response.status.value in 500..599
        else -> false
    }

    private fun toUserFriendlyException(e: Exception): SpeakNodeApiException = when (e) {
        is SpeakNodeApiException -> e
        is ConnectException ->
            SpeakNodeApiException("서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인하세요.", e)
        is java.net.SocketTimeoutException, is io.ktor.client.plugins.HttpRequestTimeoutException ->
            SpeakNodeApiException("서버 응답 시간이 초과되었습니다. 네트워크 상태를 확인하거나 잠시 후 다시 시도하세요.", e)
        is ServerResponseException -> {
            val code = e.response.status.value
            when (code) {
                in 500..599 -> SpeakNodeApiException("서버 내부 오류가 발생했습니다 ($code). 잠시 후 다시 시도하세요.", e)
                404 -> SpeakNodeApiException("요청한 리소스를 찾을 수 없습니다.", e)
                400 -> SpeakNodeApiException("잘못된 요청입니다. 입력값을 확인하세요.", e)
                413 -> SpeakNodeApiException("파일이 너무 큽니다. 최대 512MB까지 지원합니다.", e)
                else -> SpeakNodeApiException("서버 오류 ($code): ${e.message}", e)
            }
        }
        is ClientRequestException -> {
            val code = e.response.status.value
            SpeakNodeApiException("요청 오류 ($code): ${e.message}", e)
        }
        else -> SpeakNodeApiException("알 수 없는 오류: ${e.message}", e)
    }

    // Health
    suspend fun health(): HealthResponse = withRetry {
        client.get("$baseUrl/health").body()
    }

    // Chat Management
    suspend fun listChats(): ChatListResponse = withRetry {
        client.get("$baseUrl/chats").body()
    }

    suspend fun createChat(chatId: String): StatusResponse = withRetry {
        client.post("$baseUrl/chats") {
            setBody(CreateChatRequest(chatId))
        }.body()
    }

    suspend fun deleteChat(chatId: String): StatusResponse = withRetry {
        client.delete("$baseUrl/chats/$chatId").body()
    }

    // Audio Analysis (no retry — long-running operation, but wrap error)
    suspend fun analyze(
        audioFile: File,
        chatId: String = "default",
        meetingTitle: String = "",
    ): AnalyzeResponse {
        try {
            return client.submitFormWithBinaryData(
                url = "$baseUrl/analyze",
                formData = formData {
                    append("file", audioFile.readBytes(), Headers.build {
                        append(HttpHeaders.ContentType, ContentType.Audio.Any.toString())
                        append(HttpHeaders.ContentDisposition, "filename=\"${audioFile.name}\"")
                    })
                    append("chat_id", chatId)
                    if (meetingTitle.isNotBlank()) {
                        append("meeting_title", meetingTitle)
                    }
                }
            ).body()
        } catch (e: Exception) {
            throw toUserFriendlyException(e)
        }
    }

    /**
     * Streaming version of [analyze] using Server-Sent Events (SSE).
     *
     * Sends progress events to [onProgress] callback as the pipeline runs,
     * then returns the final [AnalyzeResponse] when complete.
     *
     * @param onProgress callback receiving (step, percent, message) for each pipeline step
     */
    suspend fun analyzeWithProgress(
        audioFile: File,
        chatId: String = "default",
        meetingTitle: String = "",
        onProgress: (step: String, percent: Int, message: String) -> Unit = { _, _, _ -> },
    ): AnalyzeResponse {
        try {
            val statement = client.preparePost("$baseUrl/analyze/stream") {
                setBody(
                    MultiPartFormDataContent(
                        formData {
                            append("file", audioFile.readBytes(), Headers.build {
                                append(HttpHeaders.ContentType, ContentType.Audio.Any.toString())
                                append(HttpHeaders.ContentDisposition, "filename=\"${audioFile.name}\"")
                            })
                            append("chat_id", chatId)
                            if (meetingTitle.isNotBlank()) {
                                append("meeting_title", meetingTitle)
                            }
                        }
                    )
                )
                timeout {
                    requestTimeoutMillis = null
                }
            }

            return statement.execute { response ->
                val channel = response.bodyAsChannel()
                var currentEvent = ""
                var resultJson: String? = null

                while (!channel.isClosedForRead) {
                    val line = channel.readUTF8Line() ?: break

                    when {
                        line.startsWith("event:") -> {
                            currentEvent = line.removePrefix("event:").trim()
                        }
                        line.startsWith("data:") -> {
                            val data = line.removePrefix("data:").trim()
                            when (currentEvent) {
                                "error" -> {
                                    val errorObj = json.decodeFromString<JsonObject>(data)
                                    val detail = errorObj["detail"]?.jsonPrimitive?.content ?: "Unknown error"
                                    throw SpeakNodeApiException(detail)
                                }
                                "result" -> {
                                    resultJson = data
                                }
                                else -> {
                                    // Progress event (default, no named event)
                                    try {
                                        val obj = json.decodeFromString<JsonObject>(data)
                                        val step = obj["step"]?.jsonPrimitive?.content ?: ""
                                        val percent = obj["percent"]?.jsonPrimitive?.int ?: 0
                                        val message = obj["message"]?.jsonPrimitive?.content ?: ""
                                        onProgress(step, percent, message)
                                    } catch (_: Exception) {
                                        // Ignore malformed progress events
                                    }
                                }
                            }
                            // Reset event type after processing
                            currentEvent = ""
                        }
                        // Empty line = event boundary in SSE, just continue
                    }
                }

                if (resultJson != null) {
                    json.decodeFromString<AnalyzeResponse>(resultJson!!)
                } else {
                    throw SpeakNodeApiException("서버에서 분석 결과를 받지 못했습니다.")
                }
            }
        } catch (e: SpeakNodeApiException) {
            throw e
        } catch (e: Exception) {
            throw toUserFriendlyException(e)
        }
    }

    // Agent Query (retry — usually fast)
    suspend fun agentQuery(
        question: String,
        chatId: String = "default",
    ): AgentResponse = withRetry {
        client.post("$baseUrl/agent/query") {
            setBody(AgentQueryRequest(question, chatId))
        }.body()
    }

    // Meetings
    suspend fun listMeetings(
        chatId: String = "default",
    ): MeetingListResponse = withRetry {
        client.get("$baseUrl/meetings") {
            parameter("chat_id", chatId)
        }.body()
    }

    suspend fun getMeeting(
        meetingId: String,
        chatId: String = "default",
    ): MeetingDetailResponse = withRetry {
        client.get("$baseUrl/meetings/$meetingId") {
            parameter("chat_id", chatId)
        }.body()
    }

    // Graph
    suspend fun exportGraph(
        chatId: String = "default",
        includeEmbeddings: Boolean = false,
    ): GraphExportResponse = withRetry {
        client.get("$baseUrl/graph/export") {
            parameter("chat_id", chatId)
            parameter("include_embeddings", includeEmbeddings)
        }.body()
    }

    suspend fun importGraph(
        chatId: String = "default",
        graphDump: Map<String, kotlinx.serialization.json.JsonElement>,
    ): StatusResponse = withRetry {
        client.post("$baseUrl/graph/import") {
            setBody(GraphImportRequest(chatId, graphDump))
        }.body()
    }

    // Node Update
    suspend fun updateNode(
        chatId: String = "default",
        nodeType: String,
        nodeId: String,
        fields: Map<String, String>,
    ): NodeUpdateResponse = withRetry {
        client.patch("$baseUrl/nodes/update") {
            setBody(NodeUpdateRequest(chatId, nodeType, nodeId, fields))
        }.body()
    }

    // Lifecycle
    override fun close() {
        client.close()
    }
}

/** User-friendly API exception with localized message. */
class SpeakNodeApiException(
    override val message: String,
    cause: Throwable? = null,
) : Exception(message, cause)
