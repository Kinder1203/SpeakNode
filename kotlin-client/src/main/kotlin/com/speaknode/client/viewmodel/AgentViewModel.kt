package com.speaknode.client.viewmodel

import com.speaknode.client.api.SpeakNodeApi
import com.speaknode.client.api.models.AgentResponse
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Agent 대화 상태를 관리하는 ViewModel.
 *
 * 채팅별로 독립적인 대화 히스토리를 유지합니다.
 */
class AgentViewModel(
    private val api: SpeakNodeApi = SpeakNodeApi(),
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // --- 대화 히스토리 ---
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    // --- 로딩 상태 ---
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    /**
     * Agent에 질문을 전송하고 응답을 대화 히스토리에 추가합니다.
     */
    fun sendQuery(question: String, chatId: String) {
        val currentMessages = _messages.value.toMutableList()
        currentMessages.add(ChatMessage(role = "user", content = question))
        _messages.value = currentMessages

        scope.launch {
            _isLoading.value = true
            try {
                val response: AgentResponse = api.agentQuery(question, chatId)
                val updated = _messages.value.toMutableList()
                updated.add(ChatMessage(role = "assistant", content = response.answer))
                _messages.value = updated
            } catch (e: Exception) {
                val updated = _messages.value.toMutableList()
                updated.add(ChatMessage(role = "error", content = "오류: ${e.message}"))
                _messages.value = updated
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun clearHistory() {
        _messages.value = emptyList()
    }

    fun dispose() {
        scope.cancel()
        api.close()
    }
}

data class ChatMessage(
    val role: String,   // "user" | "assistant" | "error"
    val content: String,
)
