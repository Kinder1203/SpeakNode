package com.speaknode.client.viewmodel

import com.speaknode.client.api.SpeakNodeApi
import com.speaknode.client.api.models.*
import com.speaknode.client.ui.graph.GraphDisplayData
import com.speaknode.client.ui.graph.parseGraphDump
import com.speaknode.client.util.PngMetadata
import com.speaknode.client.util.ScopeUtils
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.json.*

/**
 * ViewModel managing global application state.
 *
 * - Manages server connection status, chat list, active chat, etc.
 * - Compose UI collects StateFlow for reactive rendering.
 */
class AppViewModel(
    private val api: SpeakNodeApi = SpeakNodeApi(),
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Server connection status 
    private val _serverStatus = MutableStateFlow<ServerStatus>(ServerStatus.Unknown)
    val serverStatus: StateFlow<ServerStatus> = _serverStatus.asStateFlow()

    // Chat list 
    private val _chatIds = MutableStateFlow<List<String>>(emptyList())
    val chatIds: StateFlow<List<String>> = _chatIds.asStateFlow()

    // Active chat ID 
    private val _activeChatId = MutableStateFlow("default")
    val activeChatId: StateFlow<String> = _activeChatId.asStateFlow()

    // Meeting list 
    private val _meetings = MutableStateFlow<List<MeetingSummary>>(emptyList())
    val meetings: StateFlow<List<MeetingSummary>> = _meetings.asStateFlow()

    // Analysis state 
    private val _analysisState = MutableStateFlow<AnalysisState>(AnalysisState.Idle)
    val analysisState: StateFlow<AnalysisState> = _analysisState.asStateFlow()

    // Meeting detail
    private val _meetingDetail = MutableStateFlow<MeetingDetail?>(null)
    val meetingDetail: StateFlow<MeetingDetail?> = _meetingDetail.asStateFlow()

    private val _meetingDetailLoading = MutableStateFlow(false)
    val meetingDetailLoading: StateFlow<Boolean> = _meetingDetailLoading.asStateFlow()

    // Graph data
    private val _graphData = MutableStateFlow<GraphDisplayData?>(null)
    val graphData: StateFlow<GraphDisplayData?> = _graphData.asStateFlow()

    private val _graphLoading = MutableStateFlow(false)
    val graphLoading: StateFlow<Boolean> = _graphLoading.asStateFlow()

    // Raw graph dump (for export)
    private var _rawGraphDump: JsonObject? = null

    // Error message 
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    init {
        checkServerHealth()
        loadChats()
    }

    // Actions
    fun checkServerHealth() {
        scope.launch {
            _serverStatus.value = ServerStatus.Connecting
            try {
                val resp = api.health()
                _serverStatus.value = if (resp.status == "online") ServerStatus.Connected else ServerStatus.Error
            } catch (e: Exception) {
                _serverStatus.value = ServerStatus.Error
                _error.value = "서버 연결 실패: ${e.message}"
            }
        }
    }

    fun loadChats() {
        scope.launch {
            try {
                val resp = api.listChats()
                _chatIds.value = resp.chatIds
            } catch (e: Exception) {
                _error.value = "채팅 목록 로드 실패: ${e.message}"
            }
        }
    }

    fun selectChat(chatId: String) {
        _activeChatId.value = chatId
        loadMeetings()
    }

    fun createChat(chatId: String) {
        scope.launch {
            try {
                api.createChat(chatId)
                loadChats()
                selectChat(chatId)
            } catch (e: Exception) {
                _error.value = "채팅 생성 실패: ${e.message}"
            }
        }
    }

    fun deleteChat(chatId: String) {
        scope.launch {
            try {
                api.deleteChat(chatId)
                loadChats()
                if (_activeChatId.value == chatId) {
                    _activeChatId.value = _chatIds.value.firstOrNull() ?: "default"
                }
            } catch (e: Exception) {
                _error.value = "채팅 삭제 실패: ${e.message}"
            }
        }
    }

    fun loadMeetings() {
        scope.launch {
            try {
                val resp = api.listMeetings(_activeChatId.value)
                _meetings.value = resp.meetings
            } catch (e: Exception) {
                _meetings.value = emptyList()
                _error.value = "미팅 목록 로드 실패: ${e.message}"
            }
        }
    }

    fun analyzeAudio(filePath: String, meetingTitle: String = "") {
        scope.launch {
            _analysisState.value = AnalysisState.Analyzing(step = "start", percent = 0, message = "분석 시작...")
            try {
                val file = java.io.File(filePath)
                if (!file.exists()) {
                    _error.value = "파일을 찾을 수 없습니다: $filePath"
                    _analysisState.value = AnalysisState.Idle
                    return@launch
                }
                val resp = api.analyzeWithProgress(
                    audioFile = file,
                    chatId = _activeChatId.value,
                    meetingTitle = meetingTitle,
                    onProgress = { step, percent, message ->
                        _analysisState.value = AnalysisState.Analyzing(step, percent, message)
                    },
                )
                _analysisState.value = AnalysisState.Complete(resp)
                loadMeetings()
            } catch (e: Exception) {
                _analysisState.value = AnalysisState.Error(e.message ?: "Unknown error")
                _error.value = "분석 실패: ${e.message}"
            }
        }
    }

    // ── Meeting Detail ──

    fun loadMeetingDetail(meetingId: String) {
        scope.launch {
            _meetingDetailLoading.value = true
            try {
                val resp = api.getMeeting(meetingId, _activeChatId.value)
                _meetingDetail.value = resp.meeting
            } catch (e: Exception) {
                _error.value = "미팅 상세 로드 실패: ${e.message}"
            } finally {
                _meetingDetailLoading.value = false
            }
        }
    }

    fun clearMeetingDetail() {
        _meetingDetail.value = null
    }

    // ── Graph Data ──

    fun loadGraphData() {
        scope.launch {
            _graphLoading.value = true
            try {
                val resp = api.exportGraph(_activeChatId.value)
                _rawGraphDump = resp.graphDump
                _graphData.value = parseGraphDump(resp.graphDump)
            } catch (e: Exception) {
                _error.value = "그래프 데이터 로드 실패: ${e.message}"
                _graphData.value = null
            } finally {
                _graphLoading.value = false
            }
        }
    }

    fun exportGraphJson(file: java.io.File) {
        scope.launch {
            try {
                val dump = _rawGraphDump ?: run {
                    val resp = api.exportGraph(_activeChatId.value)
                    resp.graphDump
                }
                file.writeText(dump.toString())
                _error.value = null
            } catch (e: Exception) {
                _error.value = "JSON 내보내기 실패: ${e.message}"
            }
        }
    }

    fun exportGraphPng(file: java.io.File) {
        scope.launch {
            try {
                val dump = _rawGraphDump ?: api.exportGraph(_activeChatId.value).graphDump
                val summary = _graphData.value?.summary

                // Build analysis_result JsonObject from summary
                val analysisJson = summary?.let {
                    buildJsonObject {
                        putJsonArray("topics") {
                            it.topics.forEach { t ->
                                addJsonObject {
                                    put("title", t.title)
                                    put("summary", t.summary)
                                    put("proposer", t.proposer)
                                }
                            }
                        }
                        putJsonArray("decisions") {
                            it.decisions.forEach { d -> addJsonObject { put("description", d.description) } }
                        }
                        putJsonArray("tasks") {
                            it.tasks.forEach { t ->
                                addJsonObject {
                                    put("description", t.description)
                                    put("assignee", t.assignee)
                                    put("deadline", t.deadline)
                                    put("status", t.status)
                                }
                            }
                        }
                        putJsonArray("people") {
                            it.people.forEach { p -> addJsonObject { put("name", p.name); put("role", p.role) } }
                        }
                        putJsonArray("entities") {
                            it.entities.forEach { e ->
                                addJsonObject {
                                    put("name", e.name)
                                    put("entity_type", e.entityType)
                                    put("description", e.description)
                                }
                            }
                        }
                        putJsonArray("relations") {
                            it.relations.forEach { r ->
                                addJsonObject {
                                    put("source", r.source)
                                    put("target", r.target)
                                    put("relation_type", r.relationType)
                                }
                            }
                        }
                    }
                }

                val topics = summary?.topics?.map { ScopeUtils.decode(it.title) } ?: emptyList()
                val tasks = summary?.tasks?.map { ScopeUtils.decode(it.description) } ?: emptyList()
                val stats = mapOf(
                    "Topics" to (summary?.topics?.size ?: 0),
                    "Tasks" to (summary?.tasks?.size ?: 0),
                    "Decisions" to (summary?.decisions?.size ?: 0),
                    "People" to (summary?.people?.size ?: 0),
                    "Entities" to (summary?.entities?.size ?: 0),
                )

                val pngBytes = PngMetadata.createSharePng(
                    graphDump = dump,
                    analysisResult = analysisJson,
                    topics = topics,
                    tasks = tasks,
                    stats = stats,
                )
                file.writeBytes(pngBytes)
            } catch (e: Exception) {
                _error.value = "PNG 내보내기 실패: ${e.message}"
            }
        }
    }

    fun importGraphFile(file: java.io.File) {
        scope.launch {
            try {
                val fileName = file.name.lowercase()
                when {
                    fileName.endsWith(".png") -> {
                        val result = PngMetadata.importFromPng(file)
                        if (result == null) {
                            _error.value = "이 PNG에 SpeakNode 데이터가 없습니다."
                            return@launch
                        }
                        val (graphDump, _) = result
                        // Convert JsonObject to Map<String, JsonElement> for API
                        val dumpMap = graphDump.toMap()
                        api.importGraph(_activeChatId.value, dumpMap)
                        loadMeetings()
                        loadGraphData()
                    }
                    fileName.endsWith(".json") -> {
                        val jsonStr = file.readText()
                        val jsonObj = Json.parseToJsonElement(jsonStr).jsonObject
                        val dumpMap = jsonObj.toMap()
                        api.importGraph(_activeChatId.value, dumpMap)
                        loadMeetings()
                        loadGraphData()
                    }
                    else -> {
                        _error.value = "PNG 또는 JSON 파일만 가져올 수 있습니다."
                    }
                }
            } catch (e: Exception) {
                _error.value = "가져오기 실패: ${e.message}"
            }
        }
    }

    // ── Node Update ──

    fun updateNode(nodeType: String, nodeId: String, fields: Map<String, String>) {
        scope.launch {
            try {
                api.updateNode(
                    chatId = _activeChatId.value,
                    nodeType = nodeType,
                    nodeId = nodeId,
                    fields = fields,
                )
                // Reload graph to reflect changes
                loadGraphData()
            } catch (e: Exception) {
                _error.value = "노드 업데이트 실패: ${e.message}"
            }
        }
    }

    fun clearError() {
        _error.value = null
    }

    fun dispose() {
        scope.cancel()
        api.close()
    }

    private fun JsonObject.toMap(): Map<String, JsonElement> = this.entries.associate { it.key to it.value }
}

// State Types
sealed class ServerStatus {
    data object Unknown : ServerStatus()
    data object Connecting : ServerStatus()
    data object Connected : ServerStatus()
    data object Error : ServerStatus()
}

sealed class AnalysisState {
    data object Idle : AnalysisState()
    data class Analyzing(
        val step: String = "",
        val percent: Int = 0,
        val message: String = "분석 중...",
    ) : AnalysisState()
    data class Complete(val response: AnalyzeResponse) : AnalysisState()
    data class Error(val message: String) : AnalysisState()
}
