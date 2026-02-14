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
import kotlinx.serialization.json.Json
import java.io.Closeable
import java.io.File

/**
 * HTTP client for communicating with the SpeakNode FastAPI server.
 *
 * All API endpoints are provided as coroutine-based suspend functions.
 */
class SpeakNodeApi(
    private val baseUrl: String = "http://localhost:8000",
) : Closeable {

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
            level = LogLevel.NONE  // LogLevel.INFO for debugging
        }
        install(HttpTimeout) {
            requestTimeoutMillis = 300_000   // analysis can take a long time
            connectTimeoutMillis = 10_000
        }
        defaultRequest {
            contentType(ContentType.Application.Json)
        }
    }

    // Health
    suspend fun health(): HealthResponse =
        client.get("$baseUrl/health").body()

    // Chat Management
    suspend fun listChats(): ChatListResponse =
        client.get("$baseUrl/chats").body()

    suspend fun createChat(chatId: String): StatusResponse =
        client.post("$baseUrl/chats") {
            setBody(CreateChatRequest(chatId))
        }.body()

    suspend fun deleteChat(chatId: String): StatusResponse =
        client.delete("$baseUrl/chats/$chatId").body()

    // Audio Analysis
    suspend fun analyze(
        audioFile: File,
        chatId: String = "default",
        meetingTitle: String = "",
    ): AnalyzeResponse {
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
    }

    // Agent Query
    suspend fun agentQuery(
        question: String,
        chatId: String = "default",
    ): AgentResponse =
        client.post("$baseUrl/agent/query") {
            setBody(AgentQueryRequest(question, chatId))
        }.body()

    // Meetings
    suspend fun listMeetings(
        chatId: String = "default",
    ): MeetingListResponse =
        client.get("$baseUrl/meetings") {
            parameter("chat_id", chatId)
        }.body()

    suspend fun getMeeting(
        meetingId: String,
        chatId: String = "default",
    ): MeetingDetailResponse =
        client.get("$baseUrl/meetings/$meetingId") {
            parameter("chat_id", chatId)
        }.body()

    // Graph
    suspend fun exportGraph(
        chatId: String = "default",
        includeEmbeddings: Boolean = false,
    ): GraphExportResponse =
        client.get("$baseUrl/graph/export") {
            parameter("chat_id", chatId)
            parameter("include_embeddings", includeEmbeddings)
        }.body()

    suspend fun importGraph(
        chatId: String = "default",
        graphDump: Map<String, kotlinx.serialization.json.JsonElement>,
    ): StatusResponse =
        client.post("$baseUrl/graph/import") {
            setBody(GraphImportRequest(chatId, graphDump))
        }.body()

    // Node Update
    suspend fun updateNode(
        chatId: String = "default",
        nodeType: String,
        nodeId: String,
        fields: Map<String, String>,
    ): NodeUpdateResponse =
        client.patch("$baseUrl/nodes/update") {
            setBody(NodeUpdateRequest(chatId, nodeType, nodeId, fields))
        }.body()

    // Lifecycle
    override fun close() {
        client.close()
    }
}
