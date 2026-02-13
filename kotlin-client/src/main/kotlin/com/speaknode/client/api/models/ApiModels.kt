package com.speaknode.client.api.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ================================================================
// Request Models
// ================================================================

@Serializable
data class CreateChatRequest(
    @SerialName("chat_id") val chatId: String,
)

@Serializable
data class AgentQueryRequest(
    val question: String,
    @SerialName("chat_id") val chatId: String = "default",
)

@Serializable
data class NodeUpdateRequest(
    @SerialName("chat_id") val chatId: String = "default",
    @SerialName("node_type") val nodeType: String,
    @SerialName("node_id") val nodeId: String,
    val fields: Map<String, String> = emptyMap(),
)

@Serializable
data class GraphImportRequest(
    @SerialName("chat_id") val chatId: String = "default",
    @SerialName("graph_dump") val graphDump: Map<String, kotlinx.serialization.json.JsonElement>,
)

// ================================================================
// Response Models
// ================================================================

@Serializable
data class StatusResponse(
    val status: String,
    @SerialName("chat_id") val chatId: String? = null,
    val message: String? = null,
    @SerialName("db_path") val dbPath: String? = null,
)

@Serializable
data class HealthResponse(
    val status: String,
    @SerialName("engine_ready") val engineReady: Boolean = false,
    @SerialName("chat_count") val chatCount: Int = 0,
    val version: String = "",
)

@Serializable
data class AnalyzeResponse(
    val status: String,
    @SerialName("chat_id") val chatId: String,
    @SerialName("meeting_id") val meetingId: String,
    val analysis: AnalysisResult? = null,
)

@Serializable
data class AnalysisResult(
    val topics: List<Topic> = emptyList(),
    val decisions: List<Decision> = emptyList(),
    val tasks: List<Task> = emptyList(),
    val people: List<Person> = emptyList(),
)

@Serializable
data class Topic(
    val title: String,
    val summary: String = "",
    val proposer: String = "Unknown",
)

@Serializable
data class Decision(
    val description: String,
    @SerialName("related_topic") val relatedTopic: String = "",
)

@Serializable
data class Task(
    val description: String,
    val assignee: String = "Unassigned",
    val deadline: String = "TBD",
    val status: String = "pending",
)

@Serializable
data class Person(
    val name: String,
    val role: String = "Member",
)

@Serializable
data class AgentResponse(
    val status: String,
    @SerialName("chat_id") val chatId: String,
    val question: String,
    val answer: String,
)

@Serializable
data class ChatListResponse(
    val status: String,
    @SerialName("chats") val chatIds: List<String> = emptyList(),
)

@Serializable
data class MeetingListResponse(
    val status: String,
    @SerialName("chat_id") val chatId: String,
    val meetings: List<MeetingSummary>,
)

@Serializable
data class MeetingSummary(
    val id: String,
    val title: String = "",
    val date: String = "",
    @SerialName("source_file") val sourceFile: String = "",
)

@Serializable
data class MeetingDetailResponse(
    val status: String,
    @SerialName("chat_id") val chatId: String,
    val meeting: MeetingDetail,
)

@Serializable
data class MeetingDetail(
    val id: String,
    val title: String = "",
    val date: String = "",
    @SerialName("source_file") val sourceFile: String = "",
    val topics: List<Topic> = emptyList(),
    val tasks: List<Task> = emptyList(),
    val decisions: List<Decision> = emptyList(),
    val people: List<Person> = emptyList(),
    val utterances: List<Utterance> = emptyList(),
)

@Serializable
data class Utterance(
    val id: String,
    val text: String,
    @SerialName("startTime") val startTime: Double = 0.0,
    @SerialName("endTime") val endTime: Double = 0.0,
)

@Serializable
data class GraphExportResponse(
    val status: String,
    @SerialName("chat_id") val chatId: String,
    @SerialName("graph_dump") val graphDump: kotlinx.serialization.json.JsonObject,
)

@Serializable
data class NodeUpdateResponse(
    val status: String,
    @SerialName("matched_count") val matchedCount: Int = 0,
)
