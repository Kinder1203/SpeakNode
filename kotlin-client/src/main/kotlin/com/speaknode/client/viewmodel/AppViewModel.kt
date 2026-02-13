package com.speaknode.client.viewmodel

import com.speaknode.client.api.SpeakNodeApi
import com.speaknode.client.api.models.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 애플리케이션 전역 상태를 관리하는 ViewModel.
 *
 * - 서버 연결 상태, 채팅 목록, 활성 채팅 등을 관리
 * - Compose UI에서 StateFlow를 collect하여 반응형으로 렌더링
 */
class AppViewModel(
    private val api: SpeakNodeApi = SpeakNodeApi(),
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // --- 서버 연결 상태 ---
    private val _serverStatus = MutableStateFlow<ServerStatus>(ServerStatus.Unknown)
    val serverStatus: StateFlow<ServerStatus> = _serverStatus.asStateFlow()

    // --- 채팅 목록 ---
    private val _chatIds = MutableStateFlow<List<String>>(emptyList())
    val chatIds: StateFlow<List<String>> = _chatIds.asStateFlow()

    // --- 활성 채팅 ID ---
    private val _activeChatId = MutableStateFlow("default")
    val activeChatId: StateFlow<String> = _activeChatId.asStateFlow()

    // --- 회의 목록 ---
    private val _meetings = MutableStateFlow<List<MeetingSummary>>(emptyList())
    val meetings: StateFlow<List<MeetingSummary>> = _meetings.asStateFlow()

    // --- 분석 상태 ---
    private val _analysisState = MutableStateFlow<AnalysisState>(AnalysisState.Idle)
    val analysisState: StateFlow<AnalysisState> = _analysisState.asStateFlow()

    // --- 에러 메시지 ---
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    init {
        checkServerHealth()
        loadChats()
    }

    // ================================================================
    // Actions
    // ================================================================

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
            _analysisState.value = AnalysisState.Analyzing
            try {
                val file = java.io.File(filePath)
                if (!file.exists()) {
                    _error.value = "파일을 찾을 수 없습니다: $filePath"
                    _analysisState.value = AnalysisState.Idle
                    return@launch
                }
                val resp = api.analyze(file, _activeChatId.value, meetingTitle)
                _analysisState.value = AnalysisState.Complete(resp)
                loadMeetings()
            } catch (e: Exception) {
                _analysisState.value = AnalysisState.Error(e.message ?: "Unknown error")
                _error.value = "분석 실패: ${e.message}"
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
}

// ================================================================
// State Types
// ================================================================

sealed class ServerStatus {
    data object Unknown : ServerStatus()
    data object Connecting : ServerStatus()
    data object Connected : ServerStatus()
    data object Error : ServerStatus()
}

sealed class AnalysisState {
    data object Idle : AnalysisState()
    data object Analyzing : AnalysisState()
    data class Complete(val response: AnalyzeResponse) : AnalysisState()
    data class Error(val message: String) : AnalysisState()
}
